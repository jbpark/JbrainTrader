import sys
import time
import threading
import pythoncom
import win32com.client
from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

class KiwoomAPI(QObject):
    # 스레드 안전한 재초기화를 위한 시그널
    reinit_signal = pyqtSignal()
    # [신규] 계좌 정보 새로고침 조회를 위한 시그널 (Thread-safe)
    # 파라미터: 계좌번호, 콜백, 시장타입(DOMESTIC/OVERSEAS)
    refresh_signal = pyqtSignal(str, object, str)

    # [신규] 매매 내역(일자별체결내역) 조회를 위한 시그널
    sync_trade_signal = pyqtSignal(str, str, str, object)
    # [신규] 실현 손익 조회를 위한 시그널
    sync_profit_signal = pyqtSignal(str, str, object)
    # [신규] 일자별종목별실현손익(OPT10072) 조회를 위한 시그널
    sync_opt10072_signal = pyqtSignal(str, str, object)


    def __init__(self):
        super().__init__()
        # Kiwoom API는 GUI 기반이므로 QApplication이 필요함
        self.app = QApplication.instance()
        if not self.app:
            self.app = QApplication(sys.argv)
        
        self.ocx = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
        
        # 이벤트 연결
        self.ocx.OnEventConnect.connect(self._on_event_connect)
        self.ocx.OnReceiveTrData.connect(self._on_receive_tr_data)
        self.ocx.OnReceiveRealData.connect(self._on_receive_real_data)
        self.ocx.OnReceiveMsg.connect(self._on_receive_msg)
        self.ocx.OnReceiveChejanData.connect(self._on_receive_chejan_data)
        
        # 시그널 연결 (스레드 안전한 재초기화를 위함)
        # self.reinit_signal.connect(self.reinit_ocx)
        self.refresh_signal.connect(self._handle_refresh_signal)

        self.sync_trade_signal.connect(self._handle_sync_trade_signal)
        self.sync_profit_signal.connect(self._handle_sync_profit_signal)
        self.sync_opt10072_signal.connect(self._handle_sync_opt10072_signal)

        
        self.login_callback = None
        self.tr_callback = {} # sRQName: callback
        self.real_callback = None # callback for real data
        self.chejan_callback = None # callback for execution/balance
        self.msg_callback = None # callback for API messages
        
    @pyqtSlot()
    def reinit_ocx(self):
        """OCX 컨트롤 재초기화 (opcomms.ini 서버 설정 변경 후 적용하기 위함)
        
        워커 스레드에서 직접 호출하면 충돌(Crash)이 발생하므로, 
        반드시 시그널(QueuedConnection)을 통해 메인 GUI 스레드에서 실행되어야 합니다.
        """
        print(f"[KiwoomAPI] OCX 재초기화 중 (Thread: {threading.current_thread().name})...")
        
        # 기존 OCX 해제 (QAxWidget은 close() 시 프로세스가 종료될 수 있으므로 주의)
        try:
            # signal/slot 해제 (QAxWidget 고유 시그널만) - 개별적으로 해제하여 하나가 실패해도 계속 진행
            for sig in [self.ocx.OnEventConnect, self.ocx.OnReceiveTrData, 
                       self.ocx.OnReceiveRealData, self.ocx.OnReceiveMsg, 
                       self.ocx.OnReceiveChejanData]:
                try: sig.disconnect()
                except: pass
            
            # OCX 파괴
            self.ocx.setParent(None)
            self.ocx.deleteLater()
            print("[KiwoomAPI] 기존 OCX 파괴 요청 완료")
        except Exception as e:
            print(f"[KiwoomAPI] 기존 OCX 해제 중 오류: {e}")
        
        # QApplication 이벤트 처리 (deleteLater 반영을 위해 필수)
        for _ in range(5):
            self.app.processEvents()
            time.sleep(0.05)
        
        # 새 OCX 생성 → 이 시점에 opcomms.ini를 다시 읽음
        self.ocx = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
        
        # 이벤트 재연결
        self.ocx.OnEventConnect.connect(self._on_event_connect)
        self.ocx.OnReceiveTrData.connect(self._on_receive_tr_data)
        self.ocx.OnReceiveRealData.connect(self._on_receive_real_data)
        self.ocx.OnReceiveMsg.connect(self._on_receive_msg)
        self.ocx.OnReceiveChejanData.connect(self._on_receive_chejan_data)
        
        print("[KiwoomAPI] OCX 재초기화 완료 (새 서버 설정 적용)")
        
    @pyqtSlot(str, object, str)
    def _handle_refresh_signal(self, acc_no, callback, market="DOMESTIC"):
        """메인 스레드에서 안전하게 예수금 및 보유종목 조회를 순차적으로 실행"""
        try:
            from auto_login import config as login_config
            acc_pw = getattr(login_config, "ACC_PW", login_config.USER_PW)
            
            # 1. 예수금 조회
            # rq_name에 계좌번호를 붙여 어느 계좌의 조회 결과인지 식별한다.
            # (로그인 직후 기본 계좌 자동 조회와 엔진의 REFRESH_ACCOUNT가 겹칠 때
            #  같은 rq_name이면 콜백이 덮어써지고, 결과의 계좌 귀속도 알 수 없다)
            if market == "OVERSEAS":
                # [해외] 해외주식예수금상세현황요청 (opw30009)
                self.set_input_value("계좌번호", acc_no)
                self.set_input_value("비밀번호", acc_pw)
                self.set_input_value("비밀번호입력매체구분", "00")
                # 해외 TR은 추가 입력이 필요할 수 있음
                self.comm_rq_data(f"opw30009_ref_{acc_no}", "opw30009", 0, "8000", callback=callback)

                # 2. [해외] 해외주식잔고평가상세 (opw30011)
                self.set_input_value("계좌번호", acc_no)
                self.set_input_value("비밀번호", acc_pw)
                self.set_input_value("비밀번호입력매체구분", "00")
                self.set_input_value("조회구분", "2")
                self.comm_rq_data(f"opw30011_ref_{acc_no}", "opw30011", 0, "8001", callback=callback)
            else:
                # [국내] 기업별계좌상세현황요청
                self.set_input_value("계좌번호", acc_no)
                self.set_input_value("비밀번호", acc_pw)
                self.set_input_value("비밀번호입력매체구분", "00")
                self.set_input_value("상장폐지조회구분", "0")
                self.comm_rq_data(f"opw00004_ref_{acc_no}", "opw00004", 0, "8000", callback=callback)

                # 2. [국내] 계좌평가잔고내역요청
                self.set_input_value("계좌번호", acc_no)
                self.set_input_value("비밀번호", acc_pw)
                self.set_input_value("비밀번호입력매체구분", "00")
                self.set_input_value("조회구분", "2")
                self.comm_rq_data(f"opw00018_ref_{acc_no}", "opw00018", 0, "8001", callback=callback)
        except Exception as e:
            print(f"[KiwoomAPI] Refresh Signal Error: {e}")


    @pyqtSlot(str, str, str, object)
    def _handle_sync_trade_signal(self, acc_no, date_str, ticker, callback):
        """메인 스레드에서 안전하게 일자별체결내역(opw00007) 요청"""
        try:
            # opw00007: 계좌별주문체결내역상세요청 
            # date_str 형식: YYYYMMDD
            self.set_input_value("주문일자", date_str)
            self.set_input_value("계좌번호", acc_no)
            self.set_input_value("비밀번호", "") # 공백 허용
            self.set_input_value("비밀번호입력매체구분", "00")
            self.set_input_value("조회구분", "4") # 1:주문순, 2:역순, 3:미체결, 4:체결내역만
            self.set_input_value("주식채권구분", "0") # 0:전체, 1:주식, 2:채권
            self.set_input_value("매도수구분", "0") # 0:전체, 1:매도, 2:매수
            self.set_input_value("종목코드", ticker if ticker else "")
            self.set_input_value("시작주문번호", "")
            
            # rq_name에 날짜와 계좌번호를 포함시켜 식별 가능하게 함
            rq_name = f"opw00007_{date_str}_{acc_no}"
            self.comm_rq_data(rq_name, "opw00007", 0, "8005", callback=callback)
            print(f"[KiwoomAPI] opw00007 요청 전송: {date_str} ({acc_no})")
        except Exception as e:
            print(f"[KiwoomAPI] Sync Trade Signal Error: {e}")

    @pyqtSlot(str, str, object)
    def _handle_sync_profit_signal(self, acc_no, date_str, callback):
        """메인 스레드에서 안전하게 일자별실현손익(opt10074) 요청"""
        try:
            # opt10074: 일자별실현손익요청 (계좌·일자 단위 집계값)
            self.set_input_value("계좌번호", acc_no)
            self.set_input_value("시작일자", date_str)
            self.set_input_value("종료일자", date_str)

            rq_name = f"opt10074_{date_str}_{acc_no}"
            self.comm_rq_data(rq_name, "opt10074", 0, "8006", callback=callback)
            print(f"[KiwoomAPI] opt10074 요청 전송: {date_str} ({acc_no})")
        except Exception as e:
            print(f"[KiwoomAPI] Sync Profit Signal Error: {e}")

    @pyqtSlot(str, str, object)
    def _handle_sync_opt10072_signal(self, acc_no, date_str, callback):
        """메인 스레드에서 안전하게 일자별종목별실현손익(OPT10072) 요청"""
        try:
            # OPT10072: 일자별종목별실현손익
            self.set_input_value("계좌번호", acc_no)
            self.set_input_value("종목코드", "") # 전체 종목
            self.set_input_value("시작일자", date_str) # YYYYMMDD
            
            rq_name = f"opt10072_{date_str}_{acc_no}"
            self.comm_rq_data(rq_name, "opt10072", 0, "8007", callback=callback)
            print(f"[KiwoomAPI] opt10072 요청 전송: {date_str} ({acc_no})")
        except Exception as e:
            print(f"[KiwoomAPI] Sync OPT10072 Signal Error: {e}")


    def comm_connect(self, callback=None):
        """로그인 시도"""
        # callback이 명시적으로 전달된 경우에만 갱신 (None이면 기존 콜백 유지)
        if callback is not None:
            self.login_callback = callback
        return self.ocx.dynamicCall("CommConnect()")


    def get_connect_state(self):
        """연결 상태 확인 (0: 미연결, 1: 연결됨)"""
        return self.ocx.dynamicCall("GetConnectState()")

    def get_login_info(self, tag):
        """로그인 정보 획득"""
        return self.ocx.dynamicCall("GetLoginInfo(QString)", tag)

    def get_master_code_name(self, ticker):
        """종목명 획득"""
        return self.ocx.dynamicCall("GetMasterCodeName(QString)", ticker)

    def get_master_server_market_type(self, ticker):
        """서버 구분 획득 (시장 정보 등)"""
        # 0: 코스피, 10: 코스닥 등
        return self.ocx.dynamicCall("GetMasterServerMarketType(QString)", ticker)

    def _on_event_connect(self, err_code):
        print(f"로그인 결과 코드: {err_code}")
        if self.login_callback:
            self.login_callback(err_code)
        else:
            print("[경고] login_callback이 설정되지 않아 로그인 결과를 처리하지 못합니다.")


    def set_input_value(self, id, value):
        """TR 입력값 설정"""
        self.ocx.dynamicCall("SetInputValue(QString, QString)", id, value)

    def request_minute_data(self, ticker, interval=5, callback=None):
        """분봉 데이터 요청 (opt10080)"""
        self.set_input_value("종목코드", ticker)
        self.set_input_value("틱범위", str(interval))
        self.set_input_value("수정주가구분", "1")
        return self.comm_rq_data(f"opt10080_{ticker}", "opt10080", 0, "0101", callback)

    def comm_rq_data(self, rq_name, tr_code, prev_next, screen_no, callback=None):
        """TR 데이터 요청"""
        if callback:
            self.tr_callback[rq_name] = callback
        return self.ocx.dynamicCall("CommRqData(QString, QString, int, QString)", rq_name, tr_code, prev_next, screen_no)

    def _on_receive_tr_data(self, screen_no, rq_name, tr_code, record_name, prev_next, data_len, err_code, msg_kind, prev_next_str):
        if rq_name in self.tr_callback:
            callback = self.tr_callback.pop(rq_name)
            callback(rq_name, tr_code, screen_no)

    def get_comm_data(self, tr_code, record_name, index, item_name):
        """TR 수신 데이터 획득"""
        return self.ocx.dynamicCall("GetCommData(QString, QString, int, QString)", tr_code, record_name, index, item_name).strip()

    def get_repeat_cnt(self, tr_code, record_name):
        """TR 반복 데이터 횟수(멀티로우 수) 획득"""
        return self.ocx.dynamicCall("GetRepeatCnt(QString, QString)", tr_code, record_name)

    def get_comm_data_ex(self, tr_code, record_name):
        """TR 수신 전체 데이터 2D 배열로 획득 (GetCommDataEx)"""
        # 이 함수는 [[row0_field0, row0_field1, ...], [row1_field0, ...]] 형태로 반환
        return self.ocx.dynamicCall("GetCommDataEx(QString, QString)", tr_code, record_name)

    def print_all_data(self, trcode, recordname):
        """전체 TR 데이터 동배 출력 (디버그용)"""
        print("\n===== 전체 TR 데이터 =====")
        data = self.ocx.dynamicCall(
            "GetCommDataEx(QString, QString)",
            trcode,
            recordname
        )
        for row_idx, row in enumerate(data):
            print(f"[Row {row_idx}]")
            for col_idx, col in enumerate(row):
                # 인코딩 수정 (GetCommDataEx 데이터가 깨져서 올 수 있음)
                val = col
                if isinstance(val, str):
                    try:
                        # Latin-1 등으로 오인식된 문자열을 바이트로 변환 후 cp949로 재해석
                        b = bytes([ord(c) & 0xFF for c in val])
                        val = b.decode('cp949', errors='replace').strip()
                    except:
                        pass
                print(f"Column{col_idx} : {val}")
            print("-------------------------")

    def set_real_reg(self, screen_no, ticker_list, fid_list, opt_type):

        """실시간 데이터 등록"""
        return self.ocx.dynamicCall("SetRealReg(QString, QString, QString, QString)", screen_no, ticker_list, fid_list, opt_type)

    def get_comm_real_data(self, ticker, fid):
        """실시간 데이터 획득"""
        return self.ocx.dynamicCall("GetCommRealData(QString, int)", ticker, fid).strip()

    def _on_receive_real_data(self, ticker, real_type, real_data):
        if self.real_callback:
            self.real_callback(ticker, real_type, real_data)

    def _on_receive_msg(self, screen_no, rq_name, tr_code, msg):
        # [강력 변환] Unicode 코드포인트를 바이트로 강제 변환 후 cp949로 재해석
        def _mega_fix(text):
            if not text: return text
            try:
                # 1. 이미 bytes인 경우
                if isinstance(text, bytes):
                    return text.decode('cp949', errors='replace')
                # 2. str인 경우: 각 문자의 하위 8비트를 바이트로 추출 (Latin-1/CP1252 오인식 해결)
                b = bytes([ord(c) & 0xFF for c in text])
                return b.decode('cp949', errors='replace')
            except:
                return text

        fixed_msg = _mega_fix(msg)
            
        # 식별자를 [API MSG]로 변경하여 신규 코드 반영 여부 확인
        print(f"[API MSG] {rq_name}: {fixed_msg}")
        if self.msg_callback:
            self.msg_callback(rq_name, tr_code, fixed_msg)

    def send_order(self, rq_name, screen_no, acc_no, order_type, ticker, quantity, price, hoga_type, origin_order_no):
        """주문 전송"""
        return self.ocx.dynamicCall("SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
                                    [rq_name, screen_no, acc_no, order_type, ticker, quantity, price, hoga_type, origin_order_no])

    def _on_receive_chejan_data(self, gubun, item_cnt, fid_list):
        """체결/잔고 데이터 수신"""
        if self.chejan_callback:
            self.chejan_callback(gubun, item_cnt, fid_list)

    def run_forever(self):
        """이벤트 루프 시작"""
        self.app.exec_()

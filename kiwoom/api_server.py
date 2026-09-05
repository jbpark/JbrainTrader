import sys
import threading
import time
import json
import logging
import zmq
import os
from datetime import datetime
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QThread, QTimer
import pythoncom
from kiwoom.api import KiwoomAPI

# [설정] ZeroMQ 포트
ZMQ_PUB_PORT = 5555  # Tick, Chejan, Log 송신
ZMQ_SUB_PORT = 5556  # Order, Command 수신

# auto_login 경로를 sys.path에 추가 (kiwoom_auto_login, config 임포트용)
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_AUTO_LOGIN_DIR = os.path.join(_ROOT_DIR, "auto_login")
if _AUTO_LOGIN_DIR not in sys.path:
    sys.path.insert(0, _AUTO_LOGIN_DIR)

# 콘솔 출력 인코딩 강제 설정
import io
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    elif hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
except Exception:
    pass

# logging 콘솔 핸들러: print()를 사용하여 stdout 인코딩 설정을 정확히 따름
# logging.StreamHandler는 내부 stream 참조가 reconfigure와 달라 한글이 깨질 수 있음
class _PrintHandler(logging.Handler):
    """print()를 통해 로그를 출력하는 핸들러 (인코딩 문제 방지)"""
    def emit(self, record):
        try:
            msg = self.format(record)
            print(msg, flush=True)
        except Exception:
            self.handleError(record)

# 로그 설정
_log_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')

_file_handler = logging.FileHandler("kiwoom_gateway.log", encoding='utf-8')
_file_handler.setFormatter(_log_formatter)

_print_handler = _PrintHandler()
_print_handler.setFormatter(_log_formatter)

_root_logger = logging.getLogger()
_root_logger.setLevel(logging.INFO)
_root_logger.addHandler(_file_handler)
_root_logger.addHandler(_print_handler)

def fix_kiwoom_text(text):
    """키움 API로부터 받은 텍스트의 인코딩 수정 (cp949)"""
    if not text: return text
    try:
        if isinstance(text, bytes):
            return text.decode('cp949', errors='replace')
        
        # [강력 변환] 각 문자의 하위 8비트를 바이트로 추출 후 cp949 재디코딩
        # (Latin-1, CP1252 등 어떤 인코딩으로 오인식되었든 상관없이 바이트 레벨에서 재해석)
        b = bytes([ord(c) & 0xFF for c in text])
        return b.decode('cp949', errors='replace')
    except:
        return text


# 키움증권 버전처리기 경로
OP_VERSION_UP_PATH = r"C:\OpenAPI\opversionup.exe"

# 키움증권 서버 설정 INI 경로
KIWOOM_INI_PATH = r"C:\OpenAPI\system\opcomms.ini"


def force_server_type_in_ini(is_real: bool):
    """
    C:\OpenAPI\system\opcomms.ini 파일의 서버 설정을 직접 수정합니다.

    키움 자동로그인 시 로그인 창을 띄우지 않고 이 INI 파일 값을 읽어 서버에 접속합니다.
    CommConnect() 호출 전에 이 함수를 실행하면 자동로그인도 올바른 서버로 연결됩니다.

    [STARTER]
      SERVERTYPE=0  → 실거래
      SERVERTYPE=1  → 모의투자

    [CONNECT]
      IMITATION=0   → 실거래
      IMITATION=1   → 모의투자
    """
    import configparser

    if not os.path.exists(KIWOOM_INI_PATH):
        logging.warning(f"[INI] opcomms.ini 파일을 찾을 수 없습니다: {KIWOOM_INI_PATH}")
        return False

    try:
        # INI 파일 읽기 (키움 INI는 섹션 헤더가 있으나 키=값 형식)
        config = configparser.RawConfigParser()
        config.optionxform = str  # 대소문자 보존
        config.read(KIWOOM_INI_PATH, encoding='cp949')

        server_val = "0" if is_real else "1"  # 0=실거래, 1=모의투자
        imitation_val = "0" if is_real else "1"
        vts_val = "0" if is_real else "1"     # Virtual Trading System 사용 여부
        mode_label = "실거래(REAL)" if is_real else "모의투자(MOCK)"

        changed = False

        if config.has_section("STARTER"):
            # SERVERTYPE 변경
            old_srv = config.get("STARTER", "SERVERTYPE", fallback=None)
            if old_srv != server_val:
                config.set("STARTER", "SERVERTYPE", server_val)
                logging.info(f"[INI] [STARTER] SERVERTYPE: {old_srv} → {server_val} ({mode_label})")
                changed = True
            
            # USE_APIVTS 변경 (Virtual Trading System)
            old_vts = config.get("STARTER", "USE_APIVTS", fallback=None)
            if old_vts != vts_val:
                config.set("STARTER", "USE_APIVTS", vts_val)
                logging.info(f"[INI] [STARTER] USE_APIVTS: {old_vts} → {vts_val} ({mode_label})")
                changed = True
        else:
            logging.warning("[INI] [STARTER] 섹션을 찾을 수 없습니다")

        if config.has_section("CONNECT"):
            old = config.get("CONNECT", "IMITATION", fallback=None)
            if old != imitation_val:
                config.set("CONNECT", "IMITATION", imitation_val)
                logging.info(f"[INI] [CONNECT] IMITATION: {old} → {imitation_val} ({mode_label})")
                changed = True
            else:
                logging.info(f"[INI] [CONNECT] IMITATION 이미 {imitation_val} ({mode_label})")
        else:
            logging.warning("[INI] [CONNECT] 섹션을 찾을 수 없습니다")

        if changed:
            with open(KIWOOM_INI_PATH, 'w', encoding='cp949') as f:
                config.write(f)
            logging.info(f"[INI] opcomms.ini 저장 완료 → {mode_label} 서버로 전환")
        else:
            logging.info(f"[INI] opcomms.ini 변경 불필요 (이미 {mode_label} 설정)")

        return True

    except Exception as e:
        logging.error(f"[INI] opcomms.ini 수정 실패: {e}", exc_info=True)
        return False


def run_opversionup():
    """
    키움증권 버전처리기(opversionup.exe)를 실행하고 완료 후 종료합니다.

    순서:
      1. 기존에 실행 중인 opversionup.exe 강제 종료
      2. opversionup.exe 실행 (버전 업데이트 확인)
      3. 10초 대기 (업데이트 처리 시간)
      4. opversionup.exe 강제 종료
      5. 2초 대기 (완전 종료 확인)
    """
    import subprocess

    if not os.path.exists(OP_VERSION_UP_PATH):
        logging.warning(f"[opversionup] 버전처리기를 찾을 수 없습니다: {OP_VERSION_UP_PATH}")
        logging.warning("[opversionup] 버전처리기 없이 로그인을 계속 진행합니다.")
        return

    # 1. 기존에 실행 중인 인스턴스 종료
    logging.info("[opversionup] 기존 실행 중인 opversionup.exe 종료 시도...")
    subprocess.run(
        ["taskkill", "/F", "/IM", "opversionup.exe"],
        capture_output=True
    )

    # 2. opversionup.exe 실행
    logging.info(f"[opversionup] 버전처리기 실행: {OP_VERSION_UP_PATH}")
    subprocess.Popen([OP_VERSION_UP_PATH])

    # 3. 업데이트 처리 대기 (10초)
    logging.info("[opversionup] 업데이트 확인을 위해 10초간 대기합니다...")
    time.sleep(10)

    # 4. opversionup.exe 강제 종료 (업그레이드 확인 팝업 포함)
    logging.info("[opversionup] opversionup.exe 종료 중...")
    subprocess.run(
        ["taskkill", "/F", "/IM", "opversionup.exe"],
        capture_output=True
    )

    # 5. 완전 종료 대기
    time.sleep(2)
    logging.info("[opversionup] 버전처리기 처리 완료")


def _auto_fill_login_window(timeout=30, mode="MOCK"):
    """
    로그인 창이 열리면 kiwoom_auto_login.py를 【별도 외부 프로세스】로 실행합니다.

    ※ 중요: 같은 프로세스 내에서 import 후 호출하면 Kiwoom 보안 레이어가
       WM_SETTEXT를 차단합니다. subprocess로 실행해야만 정상 동작합니다.
    ※ Race Condition 방지: 이 함수는 CommConnect() 호출 전에 스레드로 시작해야 합니다.
       그렇지 않으면 키움 자동로그인(2초 내 완료)으로 인해 창을 놓칠 수 있습니다.

    Args:
        timeout: 로그인 창 대기 최대 시간 (초)
        mode: "MOCK" (모의투자) 또는 "REAL" (실거래)
    """
    import subprocess
    import win32gui

    logging.info(f"[AutoLogin] 로그인 창 대기 중... (mode={mode}, 폴링간격=0.1초)")

    start = time.time()
    while time.time() - start < timeout:
        hwnd = win32gui.FindWindow(None, "Open API Login")
        if hwnd and win32gui.IsWindowVisible(hwnd):
            break
        # 부분 제목 검색
        found = [False]
        def _check(h, _):
            title = win32gui.GetWindowText(h)
            if win32gui.IsWindowVisible(h) and "Open API" in title and "Login" in title:
                found[0] = True
                return False
        win32gui.EnumWindows(_check, None)
        if found[0]:
            break
        time.sleep(0.1)  # ★ 1초→0.1초로 단축: 빠른 자동로그인 Race Condition 방지
    else:
        logging.warning("[AutoLogin] 로그인 창이 열리지 않아 자동 로그인을 건너뜁니다.")
        return

    time.sleep(0.3)  # ★ 1.5초→0.3초: 창 렌더링 대기 (너무 길면 자동로그인에 선제당함)
    logging.info(f"[AutoLogin] 로그인 창 발견! 외부 프로세스로 자동 로그인 실행 (mode={mode})")

    script_path = os.path.join(_AUTO_LOGIN_DIR, "kiwoom_auto_login.py")
    # mode 인자: MOCK → "--mock", REAL → "--real"
    mode_arg = "--mock" if mode == "MOCK" else "--real"
    try:
        # sys.executable: 현재 실행 중인 Python (32bit) 인터프리터 그대로 재사용
        result = subprocess.run(
            [sys.executable, script_path, mode_arg],
            cwd=_AUTO_LOGIN_DIR,
            timeout=60
        )
        if result.returncode == 0:
            logging.info("[AutoLogin] 자동 로그인 외부 프로세스 완료")
        else:
            logging.warning(f"[AutoLogin] 자동 로그인 프로세스 종료 코드: {result.returncode}")
    except subprocess.TimeoutExpired:
        logging.error("[AutoLogin] 자동 로그인 프로세스 시간 초과 (60초)")
    except Exception as e:
        logging.error(f"[AutoLogin] 자동 로그인 프로세스 실행 실패: {e}", exc_info=True)





class KiwoomZmqGateway:
    def __init__(self):
        self.api = KiwoomAPI()
        self.is_running = True
        self.current_account_info = None
        self.sync_results = {} # {acc_no: {date_str: {"trades": [], "profits": {}, "trades_done": False, "profits_done": False}}}


        # ZeroMQ 설정
        # 주문 명령(SEND_ORDER)과 계좌 정보가 오가는 채널이므로 반드시 루프백에만 바인딩
        # (기존 tcp://* 바인딩은 같은 네트워크의 임의 호스트가 무인증으로 주문 가능했음)
        self.context = zmq.Context()
        self.pub_socket = self.context.socket(zmq.PUB)
        self.pub_socket.bind(f"tcp://127.0.0.1:{ZMQ_PUB_PORT}")

        self.sub_socket = self.context.socket(zmq.SUB)
        self.sub_socket.bind(f"tcp://127.0.0.1:{ZMQ_SUB_PORT}")
        self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, "") # 모든 메시지 수신

        # 콜백 연결
        self.api.login_callback = self.on_login
        self.api.real_callback = self.on_real_data
        self.api.chejan_callback = self.on_chejan_data
        self.api.msg_callback = self.on_api_msg

        self.is_running = True

        # 명령 수신 스레드 시작
        self.cmd_thread = threading.Thread(target=self.receive_commands, daemon=True)
        self.cmd_thread.start()

        logging.info(f"Kiwoom ZMQ Gateway Initialized (v1.2-MegaFix). (PUB: {ZMQ_PUB_PORT}, SUB: {ZMQ_SUB_PORT})")
        logging.info("[AutoLogin] 대기 중 - Vue 프론트엔드의 '연결 설정'에서 로그인 명령을 보내세요.")

    def pub_message(self, msg_type, data):
        """ZMQ PUB으로 메시지 전송"""
        try:
            payload = {
                "type": msg_type,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                "data": data
            }
            self.pub_socket.send_json(payload)
        except Exception as e:
            logging.error(f"ZMQ Pub Error: {e}")

    def on_login(self, err_code):

        status = "SUCCESS" if err_code == 0 else f"ERROR: {err_code}"
        logging.info(f"Kiwoom Login Result: {status}")

        account_info = {"err_code": err_code, "status": status}

        if err_code == 0:
            try:
                # GetLoginInfo는 OnEventConnect 직후 바로 호출하면
                # 빈 값을 반환하는 경우가 있어 잠시 대기
                time.sleep(0.5)

                # api.py의 get_login_info() 메서드 사용
                user_id      = self.api.get_login_info("USER_ID").strip()
                user_name    = fix_kiwoom_text(self.api.get_login_info("USER_NAME")).strip()
                server_type  = self.api.get_login_info("GetServerGubun").strip()

                # 계좌 목록 조회: OCX 재초기화/서버 전환 직후에는 빈 값이 반환되는
                # 경우가 있어 ACCNO 태그 폴백 + 재시도로 보강
                acc_list_raw = ""
                for attempt in range(5):
                    acc_list_raw = self.api.get_login_info("ACCLIST").strip()
                    if not acc_list_raw:
                        acc_list_raw = self.api.get_login_info("ACCNO").strip()
                    if acc_list_raw:
                        break
                    logging.warning(f"[Login] 계좌 목록이 비어 있어 재시도 중... ({attempt + 1}/5)")
                    time.sleep(1.0)

                acc_list = [a for a in acc_list_raw.split(';') if a.strip()]
                is_mock = (server_type == "1")
                server_label = "모의투자" if is_mock else "실전"

                logging.info(f"[Login] 파싱결과 → 사용자ID={user_id}, 이름={user_name}, 계좌={acc_list}, 서버={server_label}")


                if acc_list:
                    first_acc = acc_list[0]
                    self.current_account_info = {
                        "err_code": err_code,
                        "status": status,
                        "user_id": user_id,
                        "user_name": user_name,
                        "acc_no": first_acc,
                        "acc_list": acc_list,
                        "is_mock": is_mock,
                        "server_label": server_label,
                        "balance": 0,
                        "holdings": []
                    }
                    # 먼저 계정 리스트 정보를 보냄
                    self.pub_message("LOGIN_RESULT", self.current_account_info)

                    # 시그널을 통해 메인 스레드에서 안전하게 조회 시작 (1초 딜레이)
                    logging.info(f"[Login] 계좌 정보 수집 시그널 예약 (계좌: {first_acc})")
                    QTimer.singleShot(1000, lambda: self.api.refresh_signal.emit(first_acc, self.on_receive_balance, "DOMESTIC"))
                else:
                    # 원인 진단용 추가 정보 수집
                    acc_cnt   = self.api.get_login_info("ACCOUNT_CNT").strip()
                    key_sec   = self.api.get_login_info("KEY_BSECGB").strip()   # 키보드보안 0:정상, 1:해지
                    firew_sec = self.api.get_login_info("FIREW_SECGB").strip()  # 방화벽 0:미설정, 1:설정, 2:해지
                    logging.error(f"[Login] 재시도 후에도 계좌 목록이 비어 있습니다. "
                                  f"[진단] ACCOUNT_CNT={acc_cnt!r}, KEY_BSECGB={key_sec!r}, FIREW_SECGB={firew_sec!r} "
                                  f"— OCX 세션 상태가 비정상일 수 있으므로 게이트웨이 재시작을 권장합니다.")
                    self.pub_message("LOGIN_RESULT", {
                        "err_code": err_code, "status": status, "user_id": user_id, "user_name": user_name,
                        "acc_list": [], "is_mock": is_mock, "server_label": server_label
                    })



            except Exception as e:
                logging.error(f"[Login] 계좌 정보 조회 실패: {e}", exc_info=True)
                # 예외 발생 시에도 이미 보냈을 수 있지만, 한 번 더 보냄 (중복 무관)
                self.pub_message("LOGIN_RESULT", account_info)
        else:
            self.pub_message("LOGIN_RESULT", account_info)


    def on_receive_balance(self, rq_name, tr_code, screen_no):
        """예수금 조회 TR 결과 처리"""
        # rq_name 형식: opw00018_ref_<계좌번호> — 이 결과가 어느 계좌의 것인지 payload에 반영.
        # (기본 계좌 자동 조회와 다른 계좌 REFRESH가 겹쳐도 엔진이 계좌별로 구분할 수 있게 함)
        rq_acc = str(rq_name).rsplit('_', 1)[-1]
        if rq_acc.isdigit() and self.current_account_info:
            self.current_account_info["acc_no"] = rq_acc
        # [디버그] 수신된 모든 데이터 출력 (정확한 필드명 파악용)
        logging.info(f"--- TR DATA DEBUG [{tr_code}] ---")
        try:
            # 주요 요약 필드 전체 출력 시도
            all_debug_fields = [
                "예수금", "d+2추정예수금", "주문가능금액", "D+2예수금", "유가증권평가현황",
                "외화예수금", "출금가능외화금액", "외화현가금액", "원화계산금액", "원화환산금액", "원화평가금액",
                "원화대용금", "총평가금액", "총평가손익금액", "총수익률(%)"
            ]
            for field in all_debug_fields:
                val = self.api.get_comm_data(tr_code, "", 0, field)
                if val: logging.info(f"  Field[{field}] = {val}")
        except: pass

        balance = 0
        if tr_code == "opw00001":
            # 국내/통합 예수금: 필드 우선순위 (d+2추정예수금 -> 예수금 -> 주문가능금액)
            val = self.api.get_comm_data(tr_code, "", 0, "d+2추정예수금")
            if not val or int(val) == 0:
                val = self.api.get_comm_data(tr_code, "", 0, "예수금")
            if not val or int(val) == 0:
                val = self.api.get_comm_data(tr_code, "", 0, "주문가능금액")
            try: balance = int(val or 0)
            except: balance = 0
        elif tr_code == "opw00004":
            # 계좌평가현황: '예수금' 필드 사용
            val = self.api.get_comm_data(tr_code, "", 0, "예수금")
            try: balance = int(val or 0)
            except: balance = 0
        elif tr_code == "opw30009":
            # [해외] 예수금 조회 (opw30009)
            # 사용자가 달러($) 잔액을 확인하고 싶어하므로 외화 관련 필드를 최우선으로 확인
            debug_fields = ["외화예수금", "출금가능외화금액", "외화현가금액", "원화계산금액", "원화환산금액", "원화평가금액", "예수금", "d+2추정예수금"]
            for field in debug_fields:
                val = self.api.get_comm_data(tr_code, "", 0, field)
                if val: logging.info(f"  [opw30009 DEBUG] Field[{field}] = {val}")

            # 로직: 외화예수금이 있으면 그것을 사용, 없으면 원화계산금액 등 사용
            for field in ["외화예수금", "출금가능외화금액", "외화현가금액", "원화계산금액", "원화환산금액"]:
                val = self.api.get_comm_data(tr_code, "", 0, field)
                if val and float(val or 0) != 0:
                    try:
                        # 소수점을 포함한 달러 잔액을 처리하기 위해 float 사용 후 int 변환 (화면 표시 단위에 따라 조정)
                        balance = float(val) 
                        logging.info(f"  [opw30009] Selected balance from {field}: {balance}")
                        break
                    except:
                        continue
            
        elif tr_code in ["opw00018", "opw30011"]:
            # 요약 정보(Single Data) 출력
            logging.info(f"--- {tr_code} SUMMARY DEBUG ---")
            if tr_code == "opw00018":
                summary_fields = ["총매수금액", "총평가금액", "총평가손익금액", "총수익률(%)", "추정예탁자산"]
            else: # opw30011
                summary_fields = ["총매입금액", "총평가금액", "평가손익합계", "총수익률", "자산평가금액"]
            
            for field in summary_fields:
                val = self.api.get_comm_data(tr_code, rq_name, 0, field)
                if val: logging.info(f"  [Summary] {field}: {val}")

            # [디버그] 전체 TR 데이터(GetCommDataEx) 출력
            self.api.print_all_data(tr_code, rq_name)

            # 보유 종목 리스트 파싱
            holdings = []
            rows = self.api.get_repeat_cnt(tr_code, rq_name)
            
            # [로그] 수신된 로우 수 확인
            logging.info(f"[Balance/Holdings] {tr_code} (RQ:{rq_name}) 수신된 로우 수: {rows}")
            
            for i in range(rows):
                try:
                    # 해외(opw30011)는 '종목코드', 국내(opw00018)는 '종목번호'
                    ticker_field = "종목코드" if tr_code == "opw30011" else "종목번호"
                    ticker = self.api.get_comm_data(tr_code, rq_name, i, ticker_field).strip()
                    if ticker.startswith('A'): ticker = ticker[1:]
                    if not ticker: continue
                    
                    name = fix_kiwoom_text(self.api.get_comm_data(tr_code, rq_name, i, "종목명")).strip()
                    qty_raw = self.api.get_comm_data(tr_code, rq_name, i, "보유수량")
                    qty = int(float(qty_raw or 0))
                    
                    # 해외와 국내 필드명 분기 처리
                    if tr_code == "opw30011":
                        raw_p_price = self.api.get_comm_data(tr_code, rq_name, i, "매입단가")
                        raw_c_price = self.api.get_comm_data(tr_code, rq_name, i, "현재가")
                        # 매입금액은 원화환산 필드 우선 확인
                        raw_buy_amt = self.api.get_comm_data(tr_code, rq_name, i, "매입금액원화")
                        if not raw_buy_amt or float(raw_buy_amt or 0) == 0:
                            raw_buy_amt = self.api.get_comm_data(tr_code, rq_name, i, "매입금액")
                        raw_profit  = self.api.get_comm_data(tr_code, rq_name, i, "평가손익")
                        ratio_str   = self.api.get_comm_data(tr_code, rq_name, i, "수익률") or "0"
                    else:
                        raw_p_price = self.api.get_comm_data(tr_code, rq_name, i, "매입가")
                        raw_c_price = self.api.get_comm_data(tr_code, rq_name, i, "현재가")
                        raw_buy_amt = self.api.get_comm_data(tr_code, rq_name, i, "매입금액")
                        raw_profit  = self.api.get_comm_data(tr_code, rq_name, i, "평가손익")
                        ratio_str   = self.api.get_comm_data(tr_code, rq_name, i, "수익률(%)") or "0"
                    
                    buy_amt = float(raw_buy_amt or 0)
                    is_overseas = (tr_code == "opw30011")
                    
                    # 단가 계산 (안전을 위해 float 처리)
                    if qty > 0 and buy_amt > 0:
                        p_price = round(buy_amt / qty, 2 if is_overseas else 0)
                    else:
                        p_price = round(float(raw_p_price or 0), 2 if is_overseas else 0)
                        
                    c_price = round(abs(float(raw_c_price or 0)), 2 if is_overseas else 0)
                    profit = int(float(raw_profit or 0))
                    
                    try:
                        ratio = float(ratio_str)
                    except:
                        ratio = 0.0

                    # [단위 보정] 키움 TR의 수익률은 소수점 2자리가 생략된 정수로 내려온다
                    # (예: -283 = -2.83%). 매입금액과 평가손익으로 직접 계산해 % 단위로 통일.
                    if buy_amt > 0:
                        ratio = round(profit / buy_amt * 100, 2)

                    if qty > 0:
                        holdings.append({
                            "ticker": ticker,
                            "name": name,
                            "qty": qty,
                            "buy_price": p_price,
                            "current_price": c_price,
                            "profit": profit,
                            "ratio": ratio
                        })
                        logging.info(f"  - [{ticker}] {name}: {qty}주 | 매입:{p_price} | 현재:{c_price} | 손익:{profit:,} ({ratio:.2f}%)")

                except Exception as ex:
                    logging.error(f"[Login] {tr_code} 종목 파싱 중 오류 (index {i}): {ex}")
            
            logging.info(f"[Login] {tr_code} 조회 완료: {len(holdings)}개 실보유 종목 추출")
            
            if self.current_account_info:
                self.current_account_info["holdings"] = holdings
                self.pub_message("LOGIN_RESULT", self.current_account_info)
            return



        logging.info(f"[Login] [{tr_code}] 조회 완료 (RQ:{rq_name})")
        
        if self.current_account_info:
            if tr_code in ["opw00001", "opw00004"]:
                self.current_account_info["balance"] = balance
            self.pub_message("LOGIN_RESULT", self.current_account_info)

    def on_receive_trade_history(self, rq_name, tr_code, screen_no):
        """계좌별주문체결내역상세(opw00007) TR 결과 처리"""
        trades = []
        # rq_name 형식: opw00007_YYYYMMDD_ACCNO
        try:
            parts = rq_name.split('_')
            date_input = parts[1] # YYYYMMDD
            acc_no = parts[2]
            date_str = f"{date_input[:4]}-{date_input[4:6]}-{date_input[6:8]}"
        except:
            date_str = "Unknown"
            acc_no = self.current_account_info.get("acc_no") if self.current_account_info else ""

        rows = self.api.get_repeat_cnt(tr_code, rq_name)
        logging.info(f"[History] {rq_name} ({tr_code}) 수신 로우 수: {rows}")

        for i in range(rows):
            try:
                # opw00007 필드 매핑
                ticker = self.api.get_comm_data(tr_code, rq_name, i, "종목번호").strip()
                if ticker.startswith('A'): ticker = ticker[1:]
                name = fix_kiwoom_text(self.api.get_comm_data(tr_code, rq_name, i, "종목명")).strip()
                order_no = self.api.get_comm_data(tr_code, rq_name, i, "주문번호").strip()
                side = self.api.get_comm_data(tr_code, rq_name, i, "매매구분").strip() # 매수, 매도
                qty = int(self.api.get_comm_data(tr_code, rq_name, i, "체결수량") or 0)
                if qty <= 0: continue # 체결된 내역만
                
                price = int(self.api.get_comm_data(tr_code, rq_name, i, "체결단가") or 0)
                amount = price * qty
                time_raw = self.api.get_comm_data(tr_code, rq_name, i, "주문시간").strip() # HHMMSS
                
                # HHMMSS 형식 보정
                if len(time_raw) == 6:
                    exec_time = f"{date_str} {time_raw[:2]}:{time_raw[2:4]}:{time_raw[4:6]}"
                else:
                    exec_time = f"{date_str} 00:00:00"
                
                trade_item = {
                    "ticker": ticker,
                    "ticker_name": name,
                    "side": "BUY" if "매수" in side else "SELL",
                    "price": price,
                    "qty": qty,
                    "amount": amount,
                    "execution_time": exec_time,
                    "order_no": order_no,
                    "profit": 0 # 일단 0으로 초기화
                }
                trades.append(trade_item)
                logging.info(f"  - [{ticker}] {name}: {trade_item['side']} {qty}주 수신")
            except Exception as e:
                logging.error(f"[History] Row {i} parsing error: {e}")
        
        # 임시 저장
        if acc_no:
            if acc_no not in self.sync_results: self.sync_results[acc_no] = {}
            if date_str not in self.sync_results[acc_no]:
                self.sync_results[acc_no][date_str] = {"trades": [], "profits": {}, "trades_done": False, "profits_done": False}
            
            self.sync_results[acc_no][date_str]["trades"] = trades
            self.sync_results[acc_no][date_str]["trades_done"] = True
            self.finalize_sync(acc_no, date_str)
        else:
             self.pub_message("TRADES_SYNC_RESULT", {"date": date_str, "trades": trades})

    def on_receive_profit_summary(self, rq_name, tr_code, screen_no):
        """종목별실현손익상세(opw00015) TR 결과 처리"""
        try:
            parts = rq_name.split('_')
            date_input = parts[1] # YYYYMMDD
            acc_no = parts[2]
            date_str = f"{date_input[:4]}-{date_input[4:6]}-{date_input[6:8]}"
        except:
            date_str = "Unknown"
            acc_no = self.current_account_info.get("acc_no") if self.current_account_info else ""
        rows = self.api.get_repeat_cnt(tr_code, rq_name)
        profits = {} # {ticker: total_profit}
        
        logging.info(f"[Profit] {rq_name} 수신 로우 수: {rows}")
        
        for i in range(rows):
            try:
                # opw00014 필드는 종목코드 또는 종목번호일 수 있음
                ticker = self.api.get_comm_data(tr_code, rq_name, i, "종목번호").strip()
                if not ticker:
                    ticker = self.api.get_comm_data(tr_code, rq_name, i, "종목코드").strip()
                
                if ticker.startswith('A'): ticker = ticker[1:]
                
                profit_str = self.api.get_comm_data(tr_code, rq_name, i, "실현손익")
                profit = int(profit_str.strip() or 0) if profit_str else 0
                
                if ticker:
                    profits[ticker] = profit
                    logging.info(f"  - [{ticker}] 실현손익: {profit:,}")
            except Exception as e:
                logging.error(f"[Profit] Row {i} error: {e}")
        
        if acc_no:
            if acc_no not in self.sync_results: self.sync_results[acc_no] = {}
            if date_str not in self.sync_results[acc_no]:
                self.sync_results[acc_no][date_str] = {"trades": [], "profits": {}, "trades_done": False, "profits_done": False}
            
            self.sync_results[acc_no][date_str]["profits"] = profits
            self.sync_results[acc_no][date_str]["profits_done"] = True
            self.finalize_sync(acc_no, date_str)

    def on_receive_daily_profit_total(self, rq_name, tr_code, screen_no):
        """일자별실현손익(opt10074) 결과 처리 — 키움 앱과 동일한 정산 기준 일일 손익"""
        try:
            parts = rq_name.split('_')
            date_input = parts[1]  # YYYYMMDD
            acc_no = parts[2] if len(parts) > 2 else ""
            date_str = f"{date_input[:4]}-{date_input[4:6]}-{date_input[6:8]}"
        except Exception:
            date_str = "Unknown"
            acc_no = ""

        def _num(field):
            v = self.api.get_comm_data(tr_code, rq_name, 0, field).strip()
            try:
                return int(float(v or 0))
            except ValueError:
                return 0

        result = {
            "date": date_str, "acc_no": acc_no,
            "buy_amount": _num("총매수금액"), "sell_amount": _num("총매도금액"),
            "profit": _num("실현손익"), "fee": _num("매매수수료"), "tax": _num("매매세금"),
        }
        logging.info(f"[DailyTotal] opt10074 일일 실현손익(정산 기준): {result}")
        self.pub_message("DAILY_PROFIT_TOTAL", result)

    def on_receive_daily_profit_summary_opt10072(self, rq_name, tr_code, screen_no):
        """일자별종목별실현손익(OPT10072) TR 결과 처리"""
        try:
            parts = rq_name.split('_')
            date_input = parts[1] # YYYYMMDD
            date_str = f"{date_input[:4]}-{date_input[4:6]}-{date_input[6:8]}"
            acc_no = parts[2] if len(parts) > 2 else "Unknown"
        except:
            date_str = "Unknown"
            acc_no = "Unknown"

        # GetCommDataEx를 사용하여 전체 데이터를 한 번에 가져옴
        all_data = self.api.get_comm_data_ex(tr_code, rq_name)
        if not all_data:
            logging.error(f"[DailyProfit] {rq_name} 데이터가 없습니다.")
            return

        rows = len(all_data)
        logging.info(f"[DailyProfit] {rq_name} ({tr_code}) 수신 로우 수: {rows}")
        
        # 디버그: 전체 TR 데이터 출력
        self.api.print_all_data(tr_code, rq_name)
        
        summaries = []
        for i in range(rows):
            try:
                row = all_data[i]
                if len(row) < 10: continue

                # 디버그 덤프 기반 인덱스 매핑
                # Index 8: 종목코드, Index 2: 종목명, Index 3: 체결량, Index 4: 매입단가, Index 5: 체결가, Index 6: 손익, Index 7: 수익률
                ticker = row[8].strip()
                if ticker.startswith('A'): ticker = ticker[1:]
                
                # 인코딩 수정 (GetCommDataEx는 원본 바이너리가 깨져서 올 수 있으므로 고유의 텍스트 처리 필요)
                name = fix_kiwoom_text(row[2]).strip()
                
                qty = int(float(row[3] or 0))
                buy_price = float(row[4] or 0)
                sell_price = float(row[5] or 0)
                profit = int(float(row[6] or 0))
                ratio = float(row[7] or 0)
                fee = int(float(row[9] or 0))   # 당일매매수수료
                tax = int(float(row[10] or 0))  # 당일매매세금
                
                # 금액 계산
                sell_amt = int(sell_price * qty)
                
                # [보정] 매입단가가 0일 경우 역산 (매도금액 - 손익 = 매수금액)
                # 실제 매수금액에는 수수료/세금이 포함되어 있을 수 있으므로 이를 고려하여 계산
                if buy_price == 0 and qty > 0:
                    buy_amt = sell_amt - profit - fee - tax
                    buy_price = round(buy_amt / qty)
                else:
                    buy_amt = int(buy_price * qty)
                
                # 매매 데이터 형태로 정리
                summaries.append({
                    "date": date_str,
                    "ticker": ticker,
                    "ticker_name": name,
                    "buy_amount": buy_amt,
                    "sell_amount": sell_amt,
                    "amount": sell_amt,
                    "profit": profit,
                    "fee": fee,
                    "tax": tax,
                    "ratio": ratio,
                    "buy_price": buy_price,
                    "price": sell_price,
                    "qty": qty,
                    "acc_no": acc_no,
                    "order_no": f"OPT10072_{date_input}_{ticker}_{i}", # 중복 방지
                    "side": "SUMMARY",
                    "execution_time": f"{date_str} 00:00:00"
                })
                logging.info(f"  - [{ticker}] {name}: 매수:{buy_amt:,} | 매도:{sell_amt:,} | 손익:{profit:,} ({ratio}%)")
            except Exception as e:
                logging.error(f"[DailyProfit] Row {i} error: {e}")
        
        self.pub_message("TRADES_SYNC_RESULT", {"date": date_str, "acc_no": acc_no, "trades": summaries})



    def on_real_data(self, ticker, real_type, real_data):
        """실시간 틱 데이터 수신 및 PUB"""
        try:
            if real_type == "주식체결":
                # 10: 현재가, 15: 거래량, 12: 등락률 등 필요한 FID 파싱
                # Gateway는 가공 없이 원본 성격의 데이터를 최대한 빠르게 전달함
                price = abs(int(self.api.get_comm_real_data(ticker, 10)))
                volume = abs(int(self.api.get_comm_real_data(ticker, 15)))

                tick = {
                    "ticker": ticker,
                    "price": price,
                    "volume": volume,
                    "time": datetime.now().strftime("%H:%M:%S.%f")
                }
                self.pub_message("TICK", tick)
        except Exception as e:
            logging.error(f"RealData Processing Error: {e}")

    def on_chejan_data(self, gubun, item_cnt, fid_list):
        """체결/잔고 데이터 수신 및 PUB"""
        try:
            # 주요 FID 추출
            data = {
                "gubun": gubun, # '0': 주문체결, '1': 잔고
                "ticker": self.api.ocx.dynamicCall("GetChejanData(int)", 9001).strip()[1:], # 종목코드 (A005930 -> 005930)
                "name": fix_kiwoom_text(self.api.ocx.dynamicCall("GetChejanData(int)", 302)).strip(),
                "order_status": self.api.ocx.dynamicCall("GetChejanData(int)", 913).strip(), # 주문상태
                "order_qty": self.api.ocx.dynamicCall("GetChejanData(int)", 900), # 주문수량
                "filled_qty": self.api.ocx.dynamicCall("GetChejanData(int)", 911), # 체결수량
                "filled_price": self.api.ocx.dynamicCall("GetChejanData(int)", 910), # 체결가
            }
            logging.info(f"Chejan Data: {data}")
            self.pub_message("CHEJAN", data)
        except Exception as e:
            logging.error(f"Chejan Processing Error: {e}")

    def on_api_msg(self, rq_name, tr_code, msg):
        # msg는 api.py의 _mega_fix()에서 이미 cp949 → UTF-8 변환 완료된 상태
        # fix_kiwoom_text()를 다시 적용하면 이중 변환으로 깨짐 → 그대로 사용
        logging.info(f"API Msg: [{rq_name}] {msg}")
        self.pub_message("MSG", {"rq_name": rq_name, "tr_code": tr_code, "msg": msg})

    def receive_commands(self):
        """64bit 엔진으로부터 명령 수신 (SUB)"""
        logging.info("Command receiver thread started.")
        while self.is_running:
            try:
                # Non-blocking 수신 시도
                if self.sub_socket.poll(100):
                    cmd = self.sub_socket.recv_json()
                    action = cmd.get("action")
                    logging.info(f"Received Command: {action}")

                    if action == "LOGIN":
                        login_mode = cmd.get("mode", "MOCK")  # MOCK 또는 REAL
                        logging.info(f"[AutoLogin] LOGIN 명령 수신 (mode={login_mode})")

                        # 이미 로그인된 상태인지 확인
                        if self.api.get_connect_state() == 1:
                            logging.info("[AutoLogin] 이미 키움 서버에 연결되어 있습니다. 현재 계좌 정보를 재전송합니다.")
                            self.on_login(0)  # 에러코드 0(성공)으로 로그인 콜백 강제 호출
                            continue

                        def _do_login(mode):
                            is_real = (mode == "REAL")

                            # [1단계] 버전처리기 실행
                            logging.info("[AutoLogin] [1/3] 버전처리기(opversionup.exe) 실행 중...")
                            run_opversionup()

                            # [2단계] ★ 핵심: opversionup 완료 후 INI 수정
                            # opversionup.exe가 실행 중에 opcomms.ini를 덮어쓰기 때문에
                            # opversionup 완료 후에 INI를 수정해야 함!
                            logging.info(f"[AutoLogin] [2/3] opcomms.ini 서버 설정 변경 ({'실거래' if is_real else '모의투자'})...")
                            force_server_type_in_ini(is_real)

                            # [2-b단계] ★ OCX 재초기화 시그널 전송
                            # 워커 스레드에서 직접 호출하면 Crash가 발생하므로 시그널로 처리함
                            logging.info("[AutoLogin] [2/3-b] OCX 재초기화 시그널 전송 (메인 스레드에서 처리)...")
                            self.api.reinit_signal.emit()
                            
                            # 재초기화 완료를 위해 잠시 대기 (메인 스레드가 이 시그널을 처리할 시간을 줌)
                            time.sleep(1.0)

                            # [3단계] ★ 로그인 창 감시 스레드를 CommConnect 보다 먼저 시작!
                            logging.info(f"[AutoLogin] [3/3-a] 로그인 창 감시 스레드 선행 시작 (mode={mode})")
                            fill_thread = threading.Thread(
                                target=_auto_fill_login_window,
                                args=(30, mode),
                                daemon=True
                            )
                            fill_thread.start()
                            time.sleep(0.2)  # 감시 스레드가 폴링을 시작할 시간 확보

                            # [3단계] CommConnect() 호출 → 로그인 창 표시
                            logging.info("[AutoLogin] [3/3-b] CommConnect() 호출 - 로그인 창 표시 요청")
                            self.api.comm_connect(callback=None)

                            # [4단계] 창 처리 완료 대기 (최대 65초)
                            fill_thread.join(timeout=65)
                            logging.info("[AutoLogin] 로그인 창 처리 완료 (또는 타임아웃)")

                        auto_login_thread = threading.Thread(
                            target=_do_login,
                            args=(login_mode,),
                            daemon=True
                        )
                        auto_login_thread.start()

                    elif action == "REFRESH_ACCOUNT":
                        # 이미 로그인된 상태에서 특정 계좌의 정보(수익률, 잔고 등)만 다시 불러옴
                        acc_no = cmd.get("acc_no")
                        if not acc_no:
                            logging.warning("[Refresh] 계좌번호 누락")
                            continue

                        logging.info(f"[Refresh] 계좌 정보 새로고침 시그널 전송... (계좌: {acc_no}, 시장: {cmd.get('market', 'DOMESTIC')})")
                        # [핵심] KiwoomAPI 객체의 시그널을 통해 조회 요청 (메인 GUI 스레드에서 자동 처리)
                        self.api.refresh_signal.emit(acc_no, self.on_receive_balance, cmd.get("market", "DOMESTIC"))

                    elif action == "SYNC_TRADES":
                        acc_no = cmd.get("acc_no")
                        date_str = cmd.get("date") # YYYY-MM-DD -> YYYYMMDD
                        ticker = cmd.get("ticker", "")
                        
                        if not acc_no or not date_str:
                            logging.warning("[SyncTrades] 계좌번호 또는 날짜 누락")
                            continue
                        
                        kiwoom_date = date_str.replace("-", "")
                        logging.info(f"[SyncTrades] OPT10072 매매 내역 동기화 요청: {date_str} ({acc_no})")
                        
                        # OPT10072 (일자별종목별실현손익) 직접 요청
                        self.api.sync_opt10072_signal.emit(acc_no, kiwoom_date, self.on_receive_daily_profit_summary_opt10072)

                        # opt10074 (일자별실현손익)도 함께 요청 — 키움 앱과 동일한 정산 기준 합계
                        # TR 연속 조회 제한을 피하기 위해 간격을 둠
                        time.sleep(0.7)
                        self.api.sync_profit_signal.emit(acc_no, kiwoom_date, self.on_receive_daily_profit_total)

                    elif action == "SYNC_PROFIT":
                        # opt10074 (일자별실현손익) 단독 조회 — 정산 기준 일일 손익
                        acc_no = cmd.get("acc_no")
                        date_str = cmd.get("date")
                        if not acc_no or not date_str:
                            logging.warning("[SyncProfit] 계좌번호 또는 날짜 누락")
                            continue
                        kiwoom_date = date_str.replace("-", "")
                        logging.info(f"[SyncProfit] opt10074 일일 실현손익 조회: {date_str} ({acc_no})")
                        self.api.sync_profit_signal.emit(acc_no, kiwoom_date, self.on_receive_daily_profit_total)



                    elif action == "SET_REAL":

                        ticker_list = cmd.get("tickers") # "005930;000660"
                        self.api.set_real_reg("0101", ticker_list, "10;15;12", "0")
                        logging.info(f"Real data registered for: {ticker_list}")

                    elif action == "SEND_ORDER":
                        # [rq_name, screen_no, acc_no, order_type, ticker, quantity, price, hoga_type, origin_order_no]
                        args = cmd.get("args")
                        res = self.api.send_order(*args)
                        logging.info(f"Order Sent Result: {res}")
                        # 주문 접수 결과를 회신 — 클라이언트가 게이트웨이 다운/접수 실패를 감지할 수 있게 함
                        self.pub_message("ORDER_ACK", {"rq_name": args[0] if args else "", "ret": res})

                    elif action == "REQUEST_TR":
                        # TR 요청 브릿지 (필요 시 확장)
                        rq_name = cmd.get("rq_name")
                        tr_code = cmd.get("tr_code")
                        # ... 생략 (TR 종류에 따른 SetInputValue 로직 필요)

            except Exception as e:
                logging.error(f"Command processing error: {e}")
                time.sleep(1)

    def run(self):
        logging.info("Gateway Main Loop Started.")
        self.api.run_forever()

if __name__ == "__main__":
    gateway = KiwoomZmqGateway()
    gateway.run()

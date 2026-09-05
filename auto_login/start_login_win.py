import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtCore import QEventLoop

class KiwoomLogin:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.kiwoom = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
        
        # 로그인 완료 이벤트 연결
        self.kiwoom.OnEventConnect.connect(self.on_event_connect)
        
        # 로그인 창 호출
        self.kiwoom.dynamicCall("CommConnect()")
        
        # 이벤트 루프 실행
        self.app.exec_()
    
    def on_event_connect(self, err_code):
        if err_code == 0:
            print("\n" + "=" * 50)
            print("     키움증권 로그인 성공!")
            print("=" * 50)
            
            # 로그인 정보 조회
            account_list = self.kiwoom.dynamicCall("GetLoginInfo(QString)", "ACCLIST")
            server_type = self.kiwoom.dynamicCall("GetLoginInfo(QString)", "GetServerGubun")
            
            # 모의투자 여부 판별
            is_mock = (server_type == "1")
            server_str = "모의투자" if is_mock else "실거래"
            
            print(f"\n  서버 구분 : {server_str} (코드: {server_type})")
            
            # 계좌 목록 출력
            accounts = [acc for acc in account_list.split(';') if acc.strip()]
            print(f"  계좌 수   : {len(accounts)}개")
            print(f"  계좌 목록 :")
            for i, acc in enumerate(accounts, 1):
                print(f"    [{i}] {acc}")
            
            print("\n" + "=" * 50)
            print(f"  ★ 현재 {server_str} 서버에 접속 중입니다.")
            print("=" * 50)
        else:
            print(f"\n로그인 실패! (에러코드: {err_code})")
            error_messages = {
                -100: "사용자 정보 교환 실패",
                -101: "서버 접속 실패", 
                -102: "버전 처리 실패",
            }
            msg = error_messages.get(err_code, "알 수 없는 오류")
            print(f"  원인: {msg}")

if __name__ == "__main__":
    KiwoomLogin()

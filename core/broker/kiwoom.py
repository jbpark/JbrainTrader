import zmq
import json
import uuid
import time
import logging
import threading
from datetime import datetime

class KiwoomBroker:
    """
    Kiwoom Broker Client (64-bit)
    32-bit Kiwoom Gateway와 ZeroMQ를 통해 통신함.
    """
    def __init__(self, is_mock=True):
        self.is_mock = is_mock
        self.acc_no = None  # 주력 계좌번호
        
        # ZeroMQ 포트 설정
        self.ZMQ_SUB_PORT = 5555 # Gateway PUB -> Engine SUB
        self.ZMQ_PUB_PORT = 5556 # Engine PUB -> Gateway SUB
        
        self.context = zmq.Context()
        
        # SUB: 데이터 수신 (로그인 결과, 예수금, 체결 등)
        self.sub_socket = self.context.socket(zmq.SUB)
        self.sub_socket.connect(f"tcp://localhost:{self.ZMQ_SUB_PORT}")
        self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        
        # PUB: 명령 전송 (주문, 조회 요청 등)
        self.pub_socket = self.context.socket(zmq.PUB)
        self.pub_socket.connect(f"tcp://localhost:{self.ZMQ_PUB_PORT}")
        
        self.last_balance = None
        self.balance_updated_event = threading.Event()
        self.order_acks = {}  # {rq_name: {"event": Event, "ret": 접수 결과 코드}}
        
        # 백그라운드 수신 스레드 시작
        self.is_running = True
        self.receiver_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.receiver_thread.start()
        
        logging.info(f"KiwoomBroker (64bit) initialized. ZMQ Ports: {self.ZMQ_SUB_PORT}, {self.ZMQ_PUB_PORT}")

    def _receive_loop(self):
        """ZMQ 메시지 수신 루프"""
        while self.is_running:
            try:
                if self.sub_socket.poll(100):
                    msg = self.sub_socket.recv_json()
                    msg_type = msg.get("type")
                    data = msg.get("data")
                    
                    if msg_type == "LOGIN_RESULT":
                        # 예수금 및 보유종목 정보 포함됨
                        self.last_balance = data
                        self.acc_no = data.get("acc_no")
                        self.balance_updated_event.set()
                        logging.info(f"Kiwoom balance updated via LOGIN_RESULT (Acc: {self.acc_no})")
                    
                    elif msg_type == "CHEJAN":
                        # 체결/잔고 업데이트 시에도 밸런스 갱신 요청을 보낼 수 있으나
                        # 여기서는 일단 로그만 출력
                        logging.info(f"Kiwoom Chejan received: {data}")

                    elif msg_type == "ORDER_ACK":
                        rq_name = data.get("rq_name")
                        waiter = self.order_acks.get(rq_name)
                        if waiter:
                            waiter["ret"] = data.get("ret")
                            waiter["event"].set()

            except Exception as e:
                logging.error(f"KiwoomBroker receive loop error: {e}")
                time.sleep(1)

    def auth(self):
        """로그인 확인 및 시도"""
        # 게이트웨이가 이미 연결되어 있는지 확인하는 등의 로직 가능
        # 여기서는 단순히 명령을 한 번 보내보고 수신 대기하는 방식으로 처리
        self.pub_socket.send_json({"action": "LOGIN", "mode": "MOCK" if self.is_mock else "REAL"})
        
        # 결과 대기 (최대 30초)
        if self.balance_updated_event.wait(timeout=30):
            return True
        return False

    def get_balance(self):
        """주식 잔고 및 예수금 조회 (동기 방식 시뮬레이션)"""
        # 계좌번호가 없으면 게이트웨이가 요청을 응답 없이 폐기하므로 5초 대기를 낭비하지 않음
        if not self.acc_no:
            logging.warning("Kiwoom get_balance: 로그인 전(계좌번호 없음) 호출 — 요청 생략")
            return None

        self.balance_updated_event.clear()
        
        # 게이트웨이에 계좌 정보 요청
        self.pub_socket.send_json({
            "action": "REFRESH_ACCOUNT",
            "acc_no": self.acc_no if self.acc_no else "",
            "market": "DOMESTIC"
        })
        
        # 결과 대기 (최대 5초)
        if self.balance_updated_event.wait(timeout=5):
            if self.last_balance:
                # KISBroker 형식에 맞춰 반환
                return {
                    "balance": self.last_balance.get("balance", 0),
                    "holdings": self.last_balance.get("holdings", []),
                    "acc_no": self.acc_no
                }
        
        # 타임아웃 또는 데이터 없음 시 마지막 정보라도 반환
        if self.last_balance:
            return {
                "balance": self.last_balance.get("balance", 0),
                "holdings": self.last_balance.get("holdings", []),
                "acc_no": self.acc_no
            }
        return None

    def order(self, ticker, qty, price, side="BUY"):
        """주식 주문"""
        if not self.acc_no:
            logging.error("Kiwoom order failed: No account selected.")
            return None
        
        # Kiwoom send_order 파라미터 구조
        # [rq_name, screen_no, acc_no, order_type, ticker, quantity, price, hoga_type, origin_order_no]
        # order_type: 1(신규매수), 2(신규매도)
        # hoga_type: 00(지정가), 03(시장가)
        
        order_type = 1 if side == "BUY" else 2
        hoga_type = "03" # 시장가 기본 사용
        # 시장가 주문은 가격을 0으로 전송해야 함 (지정가 "00" 사용 시에만 단가 전달)
        order_price = int(price) if (hoga_type == "00" and price > 0) else 0

        rq_name = f"ORD_{uuid.uuid4().hex[:12]}"
        args = [rq_name, "0101", self.acc_no, order_type, ticker, int(qty), order_price, hoga_type, ""]

        # 게이트웨이의 접수 회신(ORDER_ACK)을 대기하여 fire-and-forget 유실을 감지
        waiter = {"event": threading.Event(), "ret": None}
        self.order_acks[rq_name] = waiter
        try:
            self.pub_socket.send_json({
                "action": "SEND_ORDER",
                "args": args
            })
            logging.info(f"Kiwoom order sent: {side} {ticker} {qty} (rq={rq_name})")

            if not waiter["event"].wait(timeout=5):
                logging.error(f"Kiwoom order NOT acknowledged (gateway down or unresponsive): {side} {ticker} {qty}")
                return None
            if waiter["ret"] != 0:
                logging.error(f"Kiwoom order rejected by API (ret={waiter['ret']}): {side} {ticker} {qty}")
                return None
            return {"rt_cd": "0", "msg1": "Order accepted by gateway"}
        finally:
            self.order_acks.pop(rq_name, None)

    def close(self):
        self.is_running = False
        # 소켓을 닫지 않고 term()을 호출하면 소켓이 전부 닫힐 때까지 영원히 블록됨
        try:
            self.sub_socket.close(linger=0)
            self.pub_socket.close(linger=0)
        except Exception:
            pass
        self.context.term()

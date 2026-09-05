import sys
import os
import threading
import queue
import logging
from datetime import datetime
from flask import Flask, request, jsonify, Response, stream_with_context, send_file
from flask_cors import CORS
import time
import asyncio
import websockets
import json
import zmq
import pytz
from cryptography.fernet import Fernet
from dotenv import load_dotenv, find_dotenv, set_key

# .env 파일 로드
load_dotenv(find_dotenv())

# 모듈 경로 문제 해결
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Discord Bot (선택적 통합 - 패키지 없거나 토큰 미설정 시 무시)
try:
    from discord_bot.bot import start_discord_bot
    DISCORD_BOT_AVAILABLE = True
except ImportError:
    DISCORD_BOT_AVAILABLE = False
    logging.debug("discord_bot 패키지 없음 - Discord Bot 비활성화")

from core.strategy import TradingStrategy
from core.database import DatabaseManager
from core.strategy_manager import StrategyManager
from core.service.collector import CollectionService
from core.broker.kis import KISBroker
from core.broker.binance import BinanceBroker

# [설정] ZeroMQ 포트 (Gateway와 연동)
ZMQ_SUB_PORT = 5555 # Gateway PUB -> Engine SUB
ZMQ_PUB_PORT = 5556 # Engine PUB -> Gateway SUB

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# WebSocket Clients and History
ws_clients = {} # {ticker: set(websocket)}
global_ws_clients = set() # all connected clients
tick_history = {} # {ticker: list}
ws_loop = None

# 로그 설정 강화 (파일 및 콘솔 동시 출력)
log_path = os.path.join(current_dir, "api_server.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [64bit Engine] %(levelname)s:%(message)s',
    handlers=[
        logging.FileHandler(log_path, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logging.info(f"Log initialized at {log_path}")

def fix_encoding(text):
    """깨진 한글(cp949 -> latin-1 오인) 복구"""
    if not text: return text
    try:
        # 이미 유효한 한글이 포함되어 있다면 건너뜀 (간단한 체크)
        if any(ord(c) > 0x80 for c in text):
            # 하지만 latin-1 범위(0x80~0xFF)의 문자가 한글 바이트인 경우가 많음
            # 시도해보고 실패하면 원래 텍스트 반환
            return text.encode('latin-1').decode('cp949')
        return text
    except:
        return text

async def ws_handler(websocket):
    global_ws_clients.add(websocket)
    logging.info(f"New WebSocket client connected. Total: {len(global_ws_clients)}")
    try:
        async for message in websocket:
            try:
                msg_data = json.loads(message)
                if msg_data.get('type') == 'subscribe':
                    ticker_raw = msg_data.get('ticker')
                    if not ticker_raw: continue
                    
                    # Ticker Normalization (safe fallback)
                    try:
                        ticker = engine_instance.db.normalize_ticker(ticker_raw) if engine_instance else ticker_raw
                    except Exception:
                        ticker = ticker_raw.split('.')[0]  # safe fallback
                    
                    if ticker not in ws_clients:
                        ws_clients[ticker] = set()
                    ws_clients[ticker].add(websocket)
                    logging.info(f"WebSocket client subscribed to {ticker} (Input: {ticker_raw})")
                    
                    # history 전송 (normalized AND raw key 둘 다 확인)
                    history = tick_history.get(ticker, tick_history.get(ticker_raw, []))
                    await websocket.send(json.dumps({
                        "type": "history",
                        "data": history
                    }))
            except Exception as e:
                logging.error(f"WS message error: {e}")
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        global_ws_clients.discard(websocket)
        for ticker in list(ws_clients.keys()):
            if websocket in ws_clients[ticker]:
                ws_clients[ticker].remove(websocket)
        logging.info(f"WebSocket client disconnected. Total: {len(global_ws_clients)}")

def start_ws_server():
    async def main():
        global ws_loop
        ws_loop = asyncio.get_running_loop()
        try:
            async with websockets.serve(ws_handler, "0.0.0.0", 8765):
                logging.info("WebSocket Server listening on ws://0.0.0.0:8765")
                await asyncio.Future()
        except Exception as e:
            logging.error(f"WebSocket server error: {e}")

    try:
        asyncio.run(main())
    except Exception as e:
        logging.error(f"Asyncio run error: {e}")

def broadcast_tick(ticker, data):
    # 항상 히스토리에 저장 (WebSocket 연결 여부와 무관)
    if ticker not in tick_history:
        tick_history[ticker] = []
    tick_history[ticker].append(data)
    if len(tick_history[ticker]) > 2000:
        tick_history[ticker].pop(0)
    
    logging.info(f"Tick stored for {ticker}: price={data.get('value')}, marker={data.get('marker')}, history_len={len(tick_history[ticker])}")

    # WebSocket 브로드캐스트 시도
    if ws_loop and ticker in ws_clients and ws_clients[ticker]:
        message = json.dumps({"type": "update", "ticker": ticker, "data": data})
        async def do_broadcast():
            active_clients = list(ws_clients[ticker])
            if active_clients:
                await asyncio.gather(*[client.send(message) for client in active_clients], return_exceptions=True)
        asyncio.run_coroutine_threadsafe(do_broadcast(), ws_loop)
        logging.info(f"Tick broadcast to {len(ws_clients[ticker])} WebSocket clients for {ticker}")
    else:
        logging.warning(f"No WebSocket clients for {ticker} (ws_loop={ws_loop is not None}, clients={ticker in ws_clients})")

def broadcast_analysis_status(message):
    if ws_loop and global_ws_clients:
        payload = json.dumps({"type": "analysis_progress", "data": message})
        async def do_broadcast():
            targets = list(global_ws_clients)
            if targets:
                await asyncio.gather(*[ws.send(payload) for ws in targets], return_exceptions=True)
        
        asyncio.run_coroutine_threadsafe(do_broadcast(), ws_loop)

class StrategyEngine:
    def __init__(self):
        self.db = DatabaseManager()
        self.strategy_mgr = StrategyManager()
        self.strategy = TradingStrategy(strategy_manager=self.strategy_mgr)
        self.config_path = os.path.join(os.path.dirname(__file__), "settings", "account_config.json")
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        
        # 계정 설정 로드 (모드별 분리 보존)
        self.accounts, self.current_mode = self.load_account_config()
        
        self.data_store = {
            "account": self.accounts[self.current_mode], # 현재 활성화된 계정 참조
            "tickers": {}
        }

        # INIT 상태로 시작 — 서비스 기동 후 auto_reconnect_last_session()이
        # 마지막 연결 정보(last_connection)로 자동 재연결을 시도함
        self.status = "INIT"
        self.logs = []
        self.collector = CollectionService(self.db)
        self.kis_broker = None 
        self.binance_broker = None
        self.simulation_stop_events = {} # {ticker: threading.Event}
        
        # ZMQ 설정
        self.zmq_context = zmq.Context()
        self.sub_socket = self.zmq_context.socket(zmq.SUB)
        self.sub_socket.connect(f"tcp://localhost:{ZMQ_SUB_PORT}")
        self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        
        self.pub_socket = self.zmq_context.socket(zmq.PUB)
        self.pub_socket.connect(f"tcp://localhost:{ZMQ_PUB_PORT}")
        # ZMQ 소켓은 스레드 안전하지 않음 — ZMQ 수신 스레드/Flask 핸들러들의 send를 직렬화
        self.zmq_send_lock = threading.Lock()

        # 스레드 시작
        threading.Thread(target=self.receive_zmq_messages, daemon=True).start()
        self.load_tickers_from_db()

    def _get_fernet(self):
        try:
            key_path = os.path.join(parent_dir, "secret.key")
            if os.path.exists(key_path):
                with open(key_path, "rb") as f:
                    return Fernet(f.read())
        except Exception as e:
            logging.error(f"Fernet 초기화 실패: {e}")
        return None

    def _get_encrypted_kis(self, mode, field):
        """ .env에서 암호화된 KIS 값을 가져와 복호화 """
        env_key = f"KIS_{mode}_{field.upper()}"
        val = os.getenv(env_key)
        if not val: return ""
        
        f = self._get_fernet()
        if not f: return val
        try:
            return f.decrypt(val.encode()).decode()
        except:
            return val

    def _set_encrypted_kis(self, mode, field, value):
        """ KIS 값을 암호화하여 .env에 저장 """
        if not value: return
        
        f = self._get_fernet()
        if not f: 
            enc_val = value
        else:
            enc_val = f.encrypt(value.encode()).decode()
            
        env_key = f"KIS_{mode}_{field.upper()}"
        dotenv_path = find_dotenv()
        if dotenv_path:
            set_key(dotenv_path, env_key, enc_val)
            # 현재 프로세스의 환경변수도 업데이트
            os.environ[env_key] = enc_val

    def _get_encrypted_kiwoom(self, field):
        """ .env에서 암호화된 Kiwoom 값을 가져와 복호화 """
        env_key = f"KIWOOM_{field.upper()}"
        val = os.getenv(env_key)
        if not val: return ""
        
        f = self._get_fernet()
        if not f: return val
        try:
            return f.decrypt(val.encode()).decode()
        except:
            return val

    def _set_encrypted_kiwoom(self, field, value):
        """ Kiwoom 값을 암호화하여 .env에 저장 """
        if not value: return
        
        f = self._get_fernet()
        if not f: 
            enc_val = value
        else:
            enc_val = f.encrypt(value.encode()).decode()
            
        env_key = f"KIWOOM_{field.upper()}"
        dotenv_path = find_dotenv()
        if dotenv_path:
            set_key(dotenv_path, env_key, enc_val)
            os.environ[env_key] = enc_val

    def _get_encrypted_discord(self, field):
        """ .env에서 암호화된 Discord 값을 가져와 복호화 """
        env_key = f"DISCORD_{field.upper()}"
        val = os.getenv(env_key)
        if not val: return ""
        
        f = self._get_fernet()
        if not f: return val
        try:
            return f.decrypt(val.encode()).decode()
        except:
            return val

    def _set_encrypted_discord(self, field, value):
        """ Discord 값을 암호화하여 .env에 저장 """
        if not value: return
        
        f = self._get_fernet()
        if not f: 
            enc_val = value
        else:
            enc_val = f.encrypt(value.encode()).decode()
            
        env_key = f"DISCORD_{field.upper()}"
        dotenv_path = find_dotenv()
        if dotenv_path:
            set_key(dotenv_path, env_key, enc_val)
            os.environ[env_key] = enc_val

    def _get_encrypted_binance(self, field):
        """ .env에서 암호화된 Binance 값을 가져와 복호화 """
        env_key = f"BINANCE_{field.upper()}"
        val = os.getenv(env_key)
        if not val: return ""

        f = self._get_fernet()
        if not f: return val
        try:
            return f.decrypt(val.encode()).decode()
        except:
            return val

    def _set_encrypted_binance(self, field, value):
        """ Binance 값을 암호화하여 .env에 저장 """
        if not value: return

        f = self._get_fernet()
        if not f:
            enc_val = value
        else:
            enc_val = f.encrypt(value.encode()).decode()

        env_key = f"BINANCE_{field.upper()}"
        dotenv_path = find_dotenv()
        if dotenv_path:
            set_key(dotenv_path, env_key, enc_val)
            os.environ[env_key] = enc_val

    def _get_encrypted_binance_market(self, market, field):
        """ .env에서 시장별(FUTURES/SPOT) 암호화된 Binance 값을 가져와 복호화 """
        env_key = f"BINANCE_{market.upper()}_{field.upper()}"
        val = os.getenv(env_key)
        if not val: return ""

        f = self._get_fernet()
        if not f: return val
        try:
            return f.decrypt(val.encode()).decode()
        except:
            return val

    def _set_encrypted_binance_market(self, market, field, value):
        """ Binance 시장별 값을 암호화하여 .env에 저장 """
        if not value: return

        f = self._get_fernet()
        if not f:
            enc_val = value
        else:
            enc_val = f.encrypt(value.encode()).decode()

        env_key = f"BINANCE_{market.upper()}_{field.upper()}"
        dotenv_path = find_dotenv()
        if dotenv_path:
            set_key(dotenv_path, env_key, enc_val)
            os.environ[env_key] = enc_val

    def load_account_config(self):
        default_accounts = {
            "REAL": {
                "acc_no": "", "name": "실전 사용자", "balance": 0, "mode": "REAL", "market": "DOMESTIC", "has_overseas": False, "broker": "KIWOOM",
                "kis_config": {
                    "app_key": self._get_encrypted_kis("REAL", "APP_KEY"),
                    "app_secret": self._get_encrypted_kis("REAL", "APP_SECRET"),
                    "acc_no": ""
                },
                "kiwoom_config": {
                    "user_id": self._get_encrypted_kiwoom("USER_ID"),
                    "user_pw": self._get_encrypted_kiwoom("USER_PW"),
                    "cert_pw": self._get_encrypted_kiwoom("CERT_PW")
                }
            },
            "MOCK": {
                "acc_no": "", "name": "모의 사용자", "balance": 0, "mode": "MOCK", "market": "DOMESTIC", "has_overseas": False, "broker": "KIWOOM",
                "kis_config": {
                    "app_key": self._get_encrypted_kis("MOCK", "APP_KEY"),
                    "app_secret": self._get_encrypted_kis("MOCK", "APP_SECRET"),
                    "acc_no": ""
                },
                "kiwoom_config": {
                    "user_id": self._get_encrypted_kiwoom("USER_ID"),
                    "user_pw": self._get_encrypted_kiwoom("USER_PW"),
                    "cert_pw": self._get_encrypted_kiwoom("CERT_PW")
                }
            },
            "VIRTUAL": {"acc_no": "VIRTUAL-001", "name": "가상 사용자", "balance": 100000000, "mode": "VIRTUAL", "market": "DOMESTIC", "has_overseas": False, "broker": "KIWOOM"},
            "discord_config": {
                "bot_token": self._get_encrypted_discord("BOT_TOKEN"),
                "guild_id": self._get_encrypted_discord("GUILD_ID"),
                "log_channel_id": self._get_encrypted_discord("LOG_CHANNEL_ID"),
                "cmd_channel_id": self._get_encrypted_discord("CMD_CHANNEL_ID")
            },
            "binance_config": {
                "futures_api_key": self._get_encrypted_binance_market("FUTURES", "API_KEY"),
                "futures_api_secret": self._get_encrypted_binance_market("FUTURES", "API_SECRET"),
                "spot_api_key": self._get_encrypted_binance_market("SPOT", "API_KEY"),
                "spot_api_secret": self._get_encrypted_binance_market("SPOT", "API_SECRET"),
                "is_testnet": False,
                "market_type": "FUTURES"
            }
        }
        current_mode = "REAL"
        # 마지막으로 성공한 연결 정보 (자동 재연결용)
        self.last_connection = None
        # 계좌별 시장 설정 {계좌번호: "DOMESTIC"|"OVERSEAS"} — 계좌 변경 시 자동 적용
        self.acc_market_prefs = {}

        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.last_connection = config.get("last_connection")
                    self.acc_market_prefs = config.get("acc_market_prefs") or {}

                    if "REAL" in config or "MOCK" in config or "VIRTUAL" in config:
                        for m in ["REAL", "MOCK", "VIRTUAL"]:
                            if m in config:
                                default_accounts[m].update(config[m])
                        current_mode = config.get("current_mode", "REAL")
                    else:
                        mode = config.get("mode", "REAL")
                        if mode in default_accounts:
                            default_accounts[mode].update(config)
                        current_mode = mode
        except Exception as e:
            logging.error(f"Error loading account config: {e}")
            
        # .env에서 로드한 KIS/Kiwoom 설정이 우선함 (계좌 정보를 암호화 저장소에 두기 위함)
        for m in ["REAL", "MOCK"]:
            default_accounts[m]["kis_config"]["app_key"] = self._get_encrypted_kis(m, "APP_KEY")
            default_accounts[m]["kis_config"]["app_secret"] = self._get_encrypted_kis(m, "APP_SECRET")
            
            # Kiwoom은 공용 (REAL/MOCK 구분 없음)
            default_accounts[m]["kiwoom_config"] = {
                "user_id": self._get_encrypted_kiwoom("USER_ID"),
                "user_pw": self._get_encrypted_kiwoom("USER_PW"),
                "cert_pw": self._get_encrypted_kiwoom("CERT_PW")
            }

        # Binance 설정 (is_testnet만 config에서 로드, API Key/Secret은 .env 우선)
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config_reload = json.load(f)
                    bn_cfg = config_reload.get("binance_config", {})
                    if "is_testnet" in bn_cfg:
                        default_accounts["binance_config"]["is_testnet"] = bn_cfg["is_testnet"]
                    if "market_type" in bn_cfg:
                        default_accounts["binance_config"]["market_type"] = bn_cfg["market_type"]
        except:
            pass

        return default_accounts, current_mode

    def save_account_config(self):
        try:
            # 전체 계정 정보와 현재 모드 저장
            # KIS Key 등 민감 정보는 마스킹 처리하여 저장
            def get_masked_acc(acc_data):
                import copy
                d = copy.deepcopy(acc_data)
                if isinstance(d.get("kis_config"), dict):
                    kis = d["kis_config"]
                    # 중첩 구조({"REAL": {...}, "MOCK": {...}})와 평면 구조({"app_key": ...}) 모두 마스킹
                    for m in ["REAL", "MOCK"]:
                        if isinstance(kis.get(m), dict):
                            for k in ["app_key", "app_secret"]:
                                if kis[m].get(k):
                                    kis[m][k] = "*****"
                    for k in ["app_key", "app_secret"]:
                        if isinstance(kis.get(k), str) and kis.get(k):
                            kis[k] = "*****"
                
                if "kiwoom_config" in d:
                    for k in ["user_id", "user_pw", "cert_pw"]:
                        if d["kiwoom_config"].get(k):
                            d["kiwoom_config"][k] = "*****"
                return d

            save_data = {
                "REAL": get_masked_acc(self.accounts["REAL"]),
                "MOCK": get_masked_acc(self.accounts["MOCK"]),
                "VIRTUAL": self.accounts["VIRTUAL"],
                "discord_config": {
                    "bot_token": "*****" if self.accounts.get("discord_config", {}).get("bot_token") else "",
                    "guild_id": "*****" if self.accounts.get("discord_config", {}).get("guild_id") else "",
                    "log_channel_id": "*****" if self.accounts.get("discord_config", {}).get("log_channel_id") else "",
                    "cmd_channel_id": "*****" if self.accounts.get("discord_config", {}).get("cmd_channel_id") else ""
                },
                "binance_config": {
                    "futures_api_key": "*****" if self.accounts.get("binance_config", {}).get("futures_api_key") else "",
                    "futures_api_secret": "*****" if self.accounts.get("binance_config", {}).get("futures_api_secret") else "",
                    "spot_api_key": "*****" if self.accounts.get("binance_config", {}).get("spot_api_key") else "",
                    "spot_api_secret": "*****" if self.accounts.get("binance_config", {}).get("spot_api_secret") else "",
                    "is_testnet": self.accounts.get("binance_config", {}).get("is_testnet", False),
                    "market_type": self.accounts.get("binance_config", {}).get("market_type", "FUTURES")
                },
                "current_mode": self.current_mode,
                "last_connection": getattr(self, "last_connection", None),
                "acc_market_prefs": getattr(self, "acc_market_prefs", {})
            }
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(save_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Error saving account config: {e}")


    def update_account(self, data):
        acc_changed = False
        if "broker" in data: self.data_store["account"]["broker"] = data["broker"]
        if "name" in data: self.data_store["account"]["name"] = data["name"]

        # 계좌별 시장 설정(국내전용/해외전용) 갱신: {"계좌번호": "DOMESTIC"|"OVERSEAS"|None}
        # None/빈 값이면 설정 해제(수동 전환 모드)
        if "acc_market_prefs" in data and isinstance(data["acc_market_prefs"], dict):
            for acc, pref in data["acc_market_prefs"].items():
                acc = str(acc).strip()
                if not acc:
                    continue
                if pref in ("DOMESTIC", "OVERSEAS"):
                    self.acc_market_prefs[acc] = pref
                    # 현재 계좌의 설정이면 시장도 즉시 전환
                    if acc == self.data_store["account"].get("acc_no") \
                            and self.data_store["account"].get("market") != pref:
                        self.data_store["account"]["market"] = pref
                        acc_changed = True  # 시장 변경 → 잔고/보유종목 재조회
                else:
                    self.acc_market_prefs.pop(acc, None)
            logging.info(f"[Engine] 계좌별 시장 설정 갱신: {self.acc_market_prefs}")

        if "acc_no" in data:
            if self.data_store["account"].get("acc_no") != data["acc_no"]:
                self.data_store["account"]["acc_no"] = data["acc_no"]
                acc_changed = True
        if acc_changed and "acc_no" in data:
            self.data_store["account"]["acc_no"] = data["acc_no"]
            # 계좌에 시장 설정(국내전용/해외전용)이 있으면 별도 선택 없이 자동 전환
            pref = self.acc_market_prefs.get(str(data["acc_no"]))
            if pref in ("DOMESTIC", "OVERSEAS") and self.data_store["account"].get("market") != pref:
                self.data_store["account"]["market"] = pref
                logging.info(f"[Engine] 계좌 시장 자동 전환: {data['acc_no']} → {pref}")
            # [수정] 가상 계좌가 아닐 때만 예수금을 0으로 초기화 (서버 조회 대기)
            if self.current_mode != "VIRTUAL":
                self.data_store["account"]["balance"] = 0
                self.data_store["account"]["holdings"] = None      # None은 '조회 중'을 의미함
                logging.info(f"[Engine] 계좌 변경 확인: {data['acc_no']} (데이터 조회 대기)")
            else:
                logging.info(f"[Engine] 가상 계좌번호 수정: {data['acc_no']} (잔액 유지)")


        
        if "balance" in data: self.data_store["account"]["balance"] = int(data["balance"])
        if "market" in data: 
            self.data_store["account"]["market"] = data["market"]
            acc_changed = True # 시장 변경 시에도 정보 새로고침 필요
        if "has_overseas" in data: self.data_store["account"]["has_overseas"] = bool(data["has_overseas"])

        # [신규] 상세 설정(API Key 등) 반영
        if "kis_config" in data:
            # kis_config 구조: {"REAL": {"app_key": "...", "app_secret": "..."}, "MOCK": {...}}
            new_kis = data["kis_config"]
            for m in ["REAL", "MOCK"]:
                if m in new_kis:
                    m_config = new_kis[m]
                    if "app_key" in m_config:
                        self._set_encrypted_kis(m, "APP_KEY", m_config["app_key"])
                        self.accounts[m]["kis_config"]["app_key"] = m_config["app_key"]
                    if "app_secret" in m_config:
                        self._set_encrypted_kis(m, "APP_SECRET", m_config["app_secret"])
                        self.accounts[m]["kis_config"]["app_secret"] = m_config["app_secret"]
                    if "acc_no" in m_config:
                        self.accounts[m]["kis_config"]["acc_no"] = m_config["acc_no"]
            
            # 현재 활성화된 브로커가 있다면 (현재 모드에 맞는 값으로) 즉시 반영
            # VIRTUAL 계정에는 kis_config가 없으므로 .get()으로 KeyError 방지
            if self.kis_broker:
                curr_kis = self.data_store["account"].get("kis_config")
                if curr_kis:
                    self.kis_broker.key = curr_kis.get("app_key", self.kis_broker.key)
                    self.kis_broker.secret = curr_kis.get("app_secret", self.kis_broker.secret)
                    logging.info(f"[Engine] KIS Broker({self.current_mode}) 설정이 실시간 업데이트되었습니다.")

        # [신규] Kiwoom 상세 설정 반영
        if "kiwoom_config" in data:
            kw_config = data["kiwoom_config"]
            if "user_id" in kw_config:
                self._set_encrypted_kiwoom("USER_ID", kw_config["user_id"])
            if "user_pw" in kw_config:
                self._set_encrypted_kiwoom("USER_PW", kw_config["user_pw"])
            if "cert_pw" in kw_config:
                self._set_encrypted_kiwoom("CERT_PW", kw_config["cert_pw"])
            
            # 모든 모드의 kiwoom_config 동기화
            for m in ["REAL", "MOCK"]:
                self.accounts[m]["kiwoom_config"] = {
                    "user_id": self._get_encrypted_kiwoom("USER_ID"),
                    "user_pw": self._get_encrypted_kiwoom("USER_PW"),
                    "cert_pw": self._get_encrypted_kiwoom("CERT_PW")
                }
            logging.info("[Engine] Kiwoom 계정 설정이 .env에 암호화되어 저장되었습니다.")

        # [신규] Discord 상세 설정 반영
        if "discord_config" in data:
            dc_config = data["discord_config"]
            if "bot_token" in dc_config: self._set_encrypted_discord("BOT_TOKEN", dc_config["bot_token"])
            if "guild_id" in dc_config: self._set_encrypted_discord("GUILD_ID", dc_config["guild_id"])
            if "log_channel_id" in dc_config: self._set_encrypted_discord("LOG_CHANNEL_ID", dc_config["log_channel_id"])
            if "cmd_channel_id" in dc_config: self._set_encrypted_discord("CMD_CHANNEL_ID", dc_config["cmd_channel_id"])
            
            self.accounts["discord_config"] = {
                "bot_token": self._get_encrypted_discord("BOT_TOKEN"),
                "guild_id": self._get_encrypted_discord("GUILD_ID"),
                "log_channel_id": self._get_encrypted_discord("LOG_CHANNEL_ID"),
                "cmd_channel_id": self._get_encrypted_discord("CMD_CHANNEL_ID")
            }
            logging.info("[Engine] Discord 설정이 .env에 암호화되어 저장되었습니다.")

        # [신규] Binance 상세 설정 반영
        if "binance_config" in data:
            bn_config = data["binance_config"]
            if "futures_api_key" in bn_config: self._set_encrypted_binance_market("FUTURES", "API_KEY", bn_config["futures_api_key"])
            if "futures_api_secret" in bn_config: self._set_encrypted_binance_market("FUTURES", "API_SECRET", bn_config["futures_api_secret"])
            if "spot_api_key" in bn_config: self._set_encrypted_binance_market("SPOT", "API_KEY", bn_config["spot_api_key"])
            if "spot_api_secret" in bn_config: self._set_encrypted_binance_market("SPOT", "API_SECRET", bn_config["spot_api_secret"])
            if "is_testnet" in bn_config:
                self.accounts["binance_config"]["is_testnet"] = bn_config["is_testnet"]

            self.accounts["binance_config"] = {
                "futures_api_key": self._get_encrypted_binance_market("FUTURES", "API_KEY"),
                "futures_api_secret": self._get_encrypted_binance_market("FUTURES", "API_SECRET"),
                "spot_api_key": self._get_encrypted_binance_market("SPOT", "API_KEY"),
                "spot_api_secret": self._get_encrypted_binance_market("SPOT", "API_SECRET"),
                "is_testnet": bn_config.get("is_testnet", self.accounts.get("binance_config", {}).get("is_testnet", False)),
                "market_type": bn_config.get("market_type", self.accounts.get("binance_config", {}).get("market_type", "FUTURES"))
            }
            logging.info("[Engine] Binance 설정이 .env에 암호화되어 저장되었습니다.")

        self.save_account_config()
        
        # [신규] 계좌번호가 변경된 경우 즉시 예수금/보유종목 조회 요청
        if acc_changed and self.status == "CONNECTED":
            broker = self.data_store["account"].get("broker", "KIWOOM")
            if broker == "KOREA_INVESTMENT" and self.kis_broker:
                logging.info(f"[Engine] KIS 계좌 정보 새로고침 요청 ({data.get('acc_no')})")
                self.kis_broker.acc_no = data.get("acc_no", self.kis_broker.acc_no)
                kis_data = self.kis_broker.get_balance()
                if kis_data:
                    self.data_store["account"]["balance"] = kis_data["balance"]
                    self.data_store["account"]["holdings"] = kis_data["holdings"]
            else:
                logging.info(f"[Engine] Kiwoom 계좌 정보 새로고침 요청 ({data.get('acc_no')})")
                self.zmq_send({
                    "action": "REFRESH_ACCOUNT",
                    "acc_no": data.get("acc_no", self.data_store["account"].get("acc_no")),
                    "market": self.data_store["account"].get("market", "DOMESTIC")
                })




    def receive_zmq_messages(self):
        logging.info("ZMQ Receiver thread started.")
        while True:
            try:
                if self.sub_socket.poll(100):
                    msg = self.sub_socket.recv_json()
                    msg_type = msg.get("type")
                    data = msg.get("data")
                    
                    if msg_type == "TICK":
                        self.process_tick(data)
                    elif msg_type == "LOGIN_RESULT":
                        err_code = data.get("err_code")
                        if err_code == 0:
                            server_label = data.get("server_label", "")
                            mode = "MOCK" if "모의" in server_label else "REAL"

                            # 이미 같은 모드로 연결된 상태에서 오는 LOGIN_RESULT는
                            # 계좌 새로고침(REFRESH_ACCOUNT 등) 응답 → 잔고/보유종목만 조용히 갱신.
                            # (전략 일시정지·계좌 재설정·로그인 성공 로그를 반복하지 않음.
                            #  전략감시(strategy_monitor)의 주기적 새로고침이 이 경로를 탄다.)
                            if self.status == "CONNECTED" and mode == self.current_mode:
                                # [중요] 다른 계좌의 조회 결과가 현재 계좌 정보를 덮어쓰지 않도록
                                # 데이터의 계좌번호가 현재 선택 계좌와 일치할 때만 반영한다.
                                # (게이트웨이는 로그인 직후 기본 계좌를 자동 조회하므로,
                                #  저장된 계좌와 다르면 빈 잔고가 덮어써지는 문제가 있었음)
                                data_acc = str(data.get("acc_no") or "")
                                cur_acc = str(self.data_store["account"].get("acc_no") or "")
                                if data_acc and cur_acc and data_acc != cur_acc:
                                    logging.info(f"[Engine] 다른 계좌({data_acc}) 조회 결과 무시 (현재 계좌: {cur_acc})")
                                    continue
                                if "holdings" in data:
                                    self.data_store["account"]["holdings"] = data["holdings"]
                                if "balance" in data:
                                    self.data_store["account"]["balance"] = data["balance"]
                                continue

                            self.status = "CONNECTED"

                            # [핵심] 서버 라벨에 따라 타겟 모드 결정 및 참조 전환
                            self.current_mode = mode
                            self.data_store["account"] = self.accounts[mode]
                            
                            user_id   = data.get("user_id", "")
                            user_name = fix_encoding(data.get("user_name", ""))
                            acc_no    = data.get("acc_no", "")
                            acc_list  = data.get("acc_list", [])

                            
                            # [추가] 해외 주식 연결 여부 판별 (계좌번호 접미사 10: 위탁종합/해외가능)
                            has_overseas = any(acc.endswith('10') for acc in acc_list)
                            self.data_store["account"]["has_overseas"] = has_overseas
                            if "market" not in self.data_store["account"]:
                                self.data_store["account"]["market"] = "DOMESTIC"


                            logging.info(f"[Engine] LOGIN_RESULT 수신 → user_id={user_id}, user_name={user_name}, acc_no={acc_no}, acc_list={acc_list}, server={server_label}")
                            
                            # [추가] 연결 성공 시 모든 전략 일시정지 처리 (사용자 요청)
                            self.db.deactivate_all_tickers()
                            for t_key in self.data_store["tickers"]:
                                self.data_store["tickers"][t_key]["paused"] = True
                                # [추가] 상태 문자열 즉시 업데이트
                                rule = self.data_store["tickers"][t_key].get("buy_rule", "DEFAULT")
                                self.data_store["tickers"][t_key]["status"] = "중지됨 (전략없음)" if (not rule or rule == 'NONE') else "중지됨"
                            logging.info("[Engine] 모든 종목 전략 일시정지 및 상태 업데이트 완료")

                            # 실제 계좌 정보로 account 업데이트
                            # [핵심] 계좌번호 결정: 이전에 저장된 번호가 목록에 있으면 그것을 우선 사용함
                            saved_acc_no = self.data_store["account"].get("acc_no")
                            
                            # name: user_name 우선, 없으면 user_id
                            display_name = user_name if user_name else user_id
                            if display_name:
                                self.data_store["account"]["name"] = display_name
                            
                            if acc_list:
                                self.data_store["account"]["acc_list"] = acc_list
                                
                                # 저장된 계좌가 목록에 있으면 그것으로 설정
                                if saved_acc_no and saved_acc_no in acc_list:
                                    logging.info(f"[Engine] 이전 계좌번호({saved_acc_no}) 복원됨")
                                    self.data_store["account"]["acc_no"] = saved_acc_no
                                    
                                    # 게이트웨이는 기본적으로 0번 계좌 조회를 시작했을 것이므로, 
                                    # 우리가 원하는 계좌로 즉시 REFRESH 요청을 보냄
                                    if saved_acc_no != acc_no: # acc_no는 게이트웨이가 보낸 기본(0번) 계좌
                                        logging.info(f"[Engine] 저장된 계좌가 기본 계좌와 다르므로 강제 새로고침 요청 ({saved_acc_no})")
                                        self.zmq_send({
                                            "action": "REFRESH_ACCOUNT",
                                            "acc_no": saved_acc_no,
                                            "market": self.data_store["account"].get("market", "DOMESTIC")
                                        })

                                else:
                                    # 저장된 계좌가 없거나 목록에 없으면 게이트웨이가 준 기본 계좌 사용
                                    if acc_no:
                                        self.data_store["account"]["acc_no"] = acc_no
                            else:
                                # [경고] 키움 계좌 목록이 비어 있으면 기존 acc_no(타 증권사 계좌일 수 있음)가
                                # 그대로 남아 매매일지 동기화 등이 조용히 실패함 → 사용자에게 알림
                                self.add_log("⚠️ 키움 계좌 목록 조회 실패 (빈 목록). 기존 계좌번호가 유지되어 "
                                             "매매내역 동기화가 동작하지 않을 수 있습니다. "
                                             "키움 게이트웨이(32bit)를 재시작한 뒤 다시 연결해 주세요.")

                            # 잔고/보유종목은 이 메시지가 현재 선택 계좌의 조회 결과일 때만 반영
                            # (게이트웨이 첫 메시지는 기본 계좌 기준이라 저장된 계좌와 다를 수 있음)
                            final_acc = str(self.data_store["account"].get("acc_no") or "")
                            msg_acc = str(data.get("acc_no") or "")
                            acc_match = not msg_acc or not final_acc or msg_acc == final_acc
                            if "holdings" in data and acc_match:
                                self.data_store["account"]["holdings"] = data["holdings"]
                            if server_label:
                                self.data_store["account"]["server"] = server_label
                                # server_label에 따른 mode 확정
                                if "모의" in server_label:
                                    self.data_store["account"]["mode"] = "MOCK"
                                elif "실전" in server_label:
                                    self.data_store["account"]["mode"] = "REAL"

                            if "balance" in data and acc_match:
                                self.data_store["account"]["balance"] = data["balance"]

                            # 자동 재연결을 위해 마지막 연결 정보 기록 (키움 로그인은 항상 주식)
                            self.last_connection = {
                                "mode": mode,
                                "asset_type": "STOCK",
                                "broker": "KIWOOM"
                            }
                            self.save_account_config()
                            self.add_log(f"로그인 성공 [{server_label}] 사용자: {display_name}, 계좌: {self.data_store['account']['acc_no']} (보유: {len(data.get('holdings', []))}개)")


                        else:
                            # 에러 코드 한글 매핑
                            error_map = {
                                -100: "사용자 정보 교환 실패 (로그인 서버 응답 없음/장외 점검)",
                                -101: "서버 접속 실패 (인터넷 연결 확인)",
                                -102: "버전 처리기 실행 실패",
                                -106: "모의투자 서버 접속 실패 (로그인 서버 확인)",
                                -200: "시세 과부하 정지",
                                -300: "주문 과부하 정지"
                            }
                            err_msg = error_map.get(err_code, f"기타 에러 (코드: {err_code})")
                            self.status = f"ERROR: {err_msg}"
                            self.add_log(f"로그인 실패: {err_msg}")
                    elif msg_type == "TRADES_SYNC_RESULT":
                        date_str = data.get("date")
                        acc_no = data.get("acc_no")
                        trades = data.get("trades", [])
                        logging.info(f"Received {len(trades)} trades for {date_str} (Acc: {acc_no}) from Kiwoom. Clearing old data...")
                        
                        # [핵심 수정] 해당 날짜, 해당 계좌의 기존 데이터를 지우고 새로 저장
                        self.db.delete_trades_by_date(date_str, acc_no=acc_no)
                        
                        saved_count = 0
                        for t in trades:
                            try:
                                self.db.save_trade(
                                    ticker=t['ticker'],
                                    ticker_name=t['ticker_name'],
                                    side=t['side'],
                                    price=t.get('price', 0),
                                    qty=t.get('qty', 0),
                                    amount=t.get('amount', t.get('sell_amount', 0)),
                                    profit=t.get('profit', 0),
                                    fee=t.get('fee', 0),
                                    tax=t.get('tax', 0),
                                    buy_amount=t.get('buy_amount', 0),
                                    buy_price=t.get('buy_price', 0),
                                    profit_rate=t.get('ratio', 0),
                                    execution_time=t['execution_time'],
                                    order_no=t['order_no'],
                                    acc_no=t.get('acc_no', acc_no)
                                )
                                saved_count += 1
                            except Exception as e:
                                logging.error(f"Error syncing trade {t['order_no']}: {e}")
                        
                        logging.info(f"Synced {saved_count} trades to database for {date_str}.")

                    elif msg_type == "DAILY_PROFIT_TOTAL":
                        # 키움 opt10074 — 정산 기준 일일 실현손익 (키움 앱 표시값과 동일)
                        d_date = data.get("date")
                        d_acc = data.get("acc_no")
                        if d_date and d_acc and d_date != "Unknown":
                            self.db.save_daily_profit_total(
                                d_date, d_acc,
                                buy_amount=data.get("buy_amount", 0),
                                sell_amount=data.get("sell_amount", 0),
                                profit=data.get("profit", 0),
                                fee=data.get("fee", 0),
                                tax=data.get("tax", 0))
                            logging.info(f"Saved daily profit total for {d_date} ({d_acc}): {data.get('profit', 0):,}")

                    elif msg_type == "CHEJAN":
                        self.add_log(f"체결 통보: {data}")
                    elif msg_type == "API_MSG":
                        self.add_log(f"[API] {data.get('msg')}")
            except Exception as e:
                logging.error(f"ZMQ error: {e}")
                time.sleep(1)

    def process_tick(self, data):
        raw_ticker = data.get("ticker")
        ticker = self.db.normalize_ticker(raw_ticker)
        price = data.get("price")
        
        # 전략 업데이트 및 매수/매도 판단
        if ticker in self.data_store["tickers"]:
            self.data_store["tickers"][ticker]["price"] = price
            self.on_ticker_update(ticker, price)

    def _get_sell_tax_rate(self, ticker, name=""):
        """매도 증권거래세율 반환. 미국 주식과 국내 상장 ETF/ETN은 면제, 국내 일반 주식은 0.2%"""
        if not str(ticker).split('.')[0].isdigit():
            return 0.0  # 미국 주식 등 비국내 종목은 국내 거래세 없음
        etf_keywords = ("KODEX", "TIGER", "ACE", "SOL", "PLUS", "KBSTAR", "RISE",
                        "ARIRANG", "HANARO", "KOSEF", "히어로즈", "ETF", "ETN")
        uname = str(name).upper()
        if any(k in uname for k in etf_keywords):
            return 0.0
        return 0.002

    def on_ticker_update(self, ticker_input, current_price, volume=0, scenario=None):
        ticker = self.db.normalize_ticker(ticker_input)
        if ticker not in self.data_store["tickers"]: return
        if self.data_store["tickers"][ticker].get("paused", False): return

        # OHLCV 데이터 업데이트 (전략 판단을 위해 필수)
        now = datetime.now()
        row = {
            'datetime': now,
            'open': current_price,
            'high': current_price,
            'low': current_price,
            'close': current_price,
            'volume': volume
        }
        self.strategy.update_data(ticker, row)

        marker = None
        last_sold_info = None
        rule_name = self.data_store["tickers"][ticker].get("buy_rule", "DEFAULT")
        name = self.data_store["tickers"][ticker].get("name", ticker)
        
        # 슬리피지 적용 (가정: 설정에 포함되어 있을 경우)
        slippage_enabled = self.data_store["tickers"][ticker].get("slippage_enabled", False)
        slippage_rate = self.data_store["tickers"][ticker].get("slippage_rate", 0.0005)
        
        # 매수/매도 신호 체크 (전략이 없거나 NONE이면 가격 모니터링만)
        if rule_name and rule_name != 'NONE':
            buy_signal = self.strategy.check_buy_signal(ticker, rule_name)
            if buy_signal:
                buy_qty = buy_signal.get('size', 1.0)
                is_us = not str(ticker).split('.')[0].isdigit()
                broker = self.data_store["account"].get("broker", "KIWOOM")
                if is_us or broker == "BINANCE":
                    qty_val = float(buy_qty)
                else:
                    # 국내 주식은 정수 주만 주문 가능. 절사 후 0주면 신호 무효화
                    qty_val = int(buy_qty)
                if qty_val <= 0:
                    logging.warning(f"[Engine] 매수 수량이 0 이하(size={buy_qty})라 매수 신호를 무시합니다: {ticker}")
                    buy_signal = None

            if buy_signal:
                marker = "B"
                if ticker not in self.strategy.positions: self.strategy.positions[ticker] = []

                # Apply slippage to buy price
                signal_price = buy_signal.get('price')
                exec_price = signal_price * (1 + slippage_rate) if slippage_enabled else signal_price

                pos = {
                    'price': exec_price,
                    'qty': qty_val,
                    'time': now,
                    'step': buy_signal.get('step', 1)
                }
                self.strategy.positions[ticker].append(pos)
                self.data_store["tickers"][ticker]["status"] = f"운용중(매수:{pos['step']})"
                log_msg = f"매수 신호 발생 [{name}] 가격: {signal_price:,}"
                if slippage_enabled: log_msg += f" (체결가: {exec_price:,.0f}, 슬리피지 반영)"
                # [신규] 실전 매매 연동 (KOREA_INVESTMENT / BINANCE)
                broker = self.data_store["account"].get("broker", "KIWOOM")
                if broker == "KOREA_INVESTMENT" and self.kis_broker and self.current_mode != "VIRTUAL":
                    logging.info(f"[Engine] KIS 실전 매수 주문 전송: {ticker}, {exec_price}")
                    order_res = self.kis_broker.order(ticker, pos['qty'], pos['price'], side="BUY")
                    if order_res:
                        self.add_log(f"KIS 주문 완료: {order_res.get('output', {}).get('ODNO', 'N/A')}")
                elif broker == "BINANCE" and self.binance_broker and self.current_mode != "VIRTUAL":
                    logging.info(f"[Engine] Binance 매수 주문 전송: {ticker}, {exec_price}")
                    order_res = self.binance_broker.order(ticker, pos['qty'], side="BUY")
                    if order_res:
                        self.add_log(f"Binance 주문 완료: OrderId={order_res.get('orderId', 'N/A')}")

                # [신규] 매매 내역 DB 저장 (BUY)
                self.db.save_trade(
                    ticker=ticker,
                    ticker_name=name,
                    side='BUY',
                    price=pos['price'],
                    qty=pos['qty'],
                    amount=pos['price'] * pos['qty'],
                    buy_price=pos['price'],
                    execution_time=now,
                    acc_no=self.data_store["account"].get("acc_no")
                )
            else:
                sell_signal = self.strategy.check_sell_signal(ticker, rule_name)
                if sell_signal:
                    marker = "S"
                    if ticker in self.strategy.positions and self.strategy.positions[ticker]:
                        pos_list = self.strategy.positions[ticker]
                        total_qty = sum(p.get('qty', 0) for p in pos_list)
                        total_cost = sum(p.get('price', 0) * p.get('qty', 0) for p in pos_list)

                        if sell_signal.get('type') == 'SELL_ALL':
                            # Apply slippage to sell price
                            exec_price = current_price * (1 - slippage_rate) if slippage_enabled else current_price
                            
                            # Kiwoom Fees: Buy Comm (0.015%), Sell Comm (0.015%) + 종목 유형별 거래세
                            buy_comm = total_cost * 0.00015
                            sell_comm = (exec_price * total_qty) * 0.00015
                            sell_tax = (exec_price * total_qty) * self._get_sell_tax_rate(ticker, name)
                            
                            raw_profit = (exec_price * total_qty) - total_cost
                            profit = raw_profit - buy_comm - sell_comm - sell_tax

                            if "realized_profit" not in self.data_store["tickers"][ticker]: self.data_store["tickers"][ticker]["realized_profit"] = 0
                            self.data_store["tickers"][ticker]["realized_profit"] += profit
                            last_sold_info = {
                                "qty": total_qty, "price": exec_price, "amount": total_qty * exec_price,
                                "profit": profit, "cumulative_profit": self.data_store["tickers"][ticker]["realized_profit"]
                            }
                            self.strategy.positions[ticker] = []
                            cum_profit = self.data_store["tickers"][ticker]["realized_profit"]
                            log_msg = f"전량 매도 발생 [{name}] 실현이익: {profit:,.0f}"
                            if slippage_enabled: log_msg += f" (체결가: {exec_price:,.0f}, 슬리피지 반영)"
                            self.add_log(log_msg + f" (누적: {cum_profit:,.0f}, 수수료/세금 반영)")

                            # [신규] 실전 매매 연동 (KOREA_INVESTMENT / BINANCE)
                            broker = self.data_store["account"].get("broker", "KIWOOM")
                            if broker == "KOREA_INVESTMENT" and self.kis_broker and self.current_mode != "VIRTUAL":
                                logging.info(f"[Engine] KIS 실전 전량 매도 주문 전송: {ticker}, {exec_price}")
                                order_res = self.kis_broker.order(ticker, total_qty, exec_price, side="SELL")
                                if order_res:
                                    self.add_log(f"KIS 주문 완료: {order_res.get('output', {}).get('ODNO', 'N/A')}")
                            elif broker == "BINANCE" and self.binance_broker and self.current_mode != "VIRTUAL":
                                logging.info(f"[Engine] Binance 전량 매도 주문 전송: {ticker}, {exec_price}")
                                order_res = self.binance_broker.order(ticker, total_qty, side="SELL")
                                if order_res:
                                    self.add_log(f"Binance 주문 완료: OrderId={order_res.get('orderId', 'N/A')}")

                            # [신규] 매매 내역 DB 저장 (SELL_ALL)
                            self.db.save_trade(
                                ticker=ticker,
                                ticker_name=name,
                                side='SELL',
                                price=exec_price,
                                qty=total_qty,
                                amount=exec_price * total_qty,
                                buy_amount=total_cost,
                                buy_price=total_cost / total_qty if total_qty > 0 else 0,
                                profit=profit,
                                fee=buy_comm + sell_comm,
                                tax=sell_tax,
                                execution_time=now,
                                acc_no=self.data_store["account"].get("acc_no"),
                                memo=f"SELL_ALL (Reason: {sell_signal.get('reason', 'SIGNAL')})"
                            )
                        else:
                            # 신호의 size(주 수)만큼 최근 매수분(LIFO)에서 차감하여 부분 매도
                            sell_size = sell_signal.get('size', 1.0)
                            is_us = not str(ticker).split('.')[0].isdigit()
                            broker = self.data_store["account"].get("broker", "KIWOOM")
                            if is_us or broker == "BINANCE":
                                qty = min(float(sell_size), total_qty)
                            else:
                                qty = min(int(sell_size), total_qty)

                            if qty <= 0:
                                logging.warning(f"[Engine] 매도 수량이 0 이하(size={sell_size})라 매도 신호를 무시합니다: {ticker}")
                            else:
                                # LIFO 차감하며 매도분 원가 산출
                                sold_cost = 0.0
                                remaining = qty
                                while remaining > 0 and pos_list:
                                    last_pos = pos_list[-1]
                                    take = min(last_pos.get('qty', 0), remaining)
                                    sold_cost += take * last_pos.get('price', 0)
                                    last_pos['qty'] = last_pos.get('qty', 0) - take
                                    remaining -= take
                                    if last_pos.get('qty', 0) <= 0:
                                        pos_list.pop()
                                buy_price = sold_cost / qty

                                # Apply slippage to sell price
                                exec_price = current_price * (1 - slippage_rate) if slippage_enabled else current_price

                                # Kiwoom Fees: Buy Comm (0.015%), Sell Comm (0.015%) + 종목 유형별 거래세
                                buy_comm = sold_cost * 0.00015
                                sell_comm = (exec_price * qty) * 0.00015
                                sell_tax = (exec_price * qty) * self._get_sell_tax_rate(ticker, name)

                                raw_profit = (exec_price * qty) - sold_cost
                                profit = raw_profit - buy_comm - sell_comm - sell_tax

                                if "realized_profit" not in self.data_store["tickers"][ticker]: self.data_store["tickers"][ticker]["realized_profit"] = 0
                                self.data_store["tickers"][ticker]["realized_profit"] += profit
                                last_sold_info = {
                                    "qty": qty, "price": exec_price, "amount": qty * exec_price,
                                    "profit": profit, "cumulative_profit": self.data_store["tickers"][ticker]["realized_profit"]
                                }
                                cum_profit = self.data_store["tickers"][ticker]["realized_profit"]
                                log_msg = f"부분 매도 발생 [{name}] {qty}주, 실현이익: {profit:,.0f}"
                                if slippage_enabled: log_msg += f" (체결가: {exec_price:,.0f}, 슬리피지 반영)"
                                self.add_log(log_msg + f" (누적: {cum_profit:,.0f}, 수수료/세금 반영)")

                                # [신규] 실전 매매 연동 (KOREA_INVESTMENT / BINANCE)
                                if broker == "KOREA_INVESTMENT" and self.kis_broker and self.current_mode != "VIRTUAL":
                                    logging.info(f"[Engine] KIS 실전 부분 매도 주문 전송: {ticker}, {exec_price}")
                                    order_res = self.kis_broker.order(ticker, qty, exec_price, side="SELL")
                                    if order_res:
                                        self.add_log(f"KIS 주문 완료: {order_res.get('output', {}).get('ODNO', 'N/A')}")
                                elif broker == "BINANCE" and self.binance_broker and self.current_mode != "VIRTUAL":
                                    logging.info(f"[Engine] Binance 부분 매도 주문 전송: {ticker}, {exec_price}")
                                    order_res = self.binance_broker.order(ticker, qty, side="SELL")
                                    if order_res:
                                        self.add_log(f"Binance 주문 완료: OrderId={order_res.get('orderId', 'N/A')}")

                                # [신규] 부분 매도 내역 DB 저장
                                self.db.save_trade(
                                    ticker=ticker,
                                    ticker_name=name,
                                    side='SELL',
                                    price=exec_price,
                                    qty=qty,
                                    amount=exec_price * qty,
                                    buy_amount=sold_cost,
                                    buy_price=buy_price,
                                    profit=profit,
                                    fee=buy_comm + sell_comm,
                                    tax=sell_tax,
                                    execution_time=now,
                                    acc_no=self.data_store["account"].get("acc_no"),
                                    memo=f"PART_SELL (Reason: {sell_signal.get('reason', 'SIGNAL')})"
                                )
                    else:
                        # sell signal but no pos
                        self.data_store["tickers"][ticker]["status"] = "운용중"
                else:
                    # not sell signal
                    has_pos = ticker in self.strategy.positions and self.strategy.positions[ticker]
                    self.data_store["tickers"][ticker]["status"] = "운용중(보유)" if has_pos else "운용중"
        else:
            self.data_store["tickers"][ticker]["status"] = "중지됨 (전략없음)"

        # 보유 수량 및 평균 단가 업데이트
        pos_list = self.strategy.positions.get(ticker, [])
        if pos_list:
            total_qty = sum(p.get('qty', 0) for p in pos_list)
            total_cost = sum(p.get('price', 0) * p.get('qty', 0) for p in pos_list)
            self.data_store["tickers"][ticker]["position_qty"] = total_qty
            self.data_store["tickers"][ticker]["avg_price"] = total_cost / total_qty
        else:
            self.data_store["tickers"][ticker]["position_qty"] = 0
            self.data_store["tickers"][ticker]["avg_price"] = 0

        # WS 브로드캐스트
        tick_data = {
            "time": int(time.time() * 1000), 
            "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "value": current_price, 
            "volume": volume,
            "scenario": scenario,
            "marker": marker
        }
        if last_sold_info: tick_data.update(last_sold_info)
        broadcast_tick(ticker, tick_data)

    def load_tickers_from_db(self):
        tickers = self.db.get_tickers()
        db_tickers = {self.db.normalize_ticker(t['ticker']): t for t in tickers}
        
        # 1. DB에 없는 티커 메모리에서 삭제 (중복 방지 및 정합성 유지)
        for m_ticker in list(self.data_store["tickers"].keys()):
            if m_ticker not in db_tickers:
                logging.info(f"Removing orphaned ticker from memory: {m_ticker}")
                del self.data_store["tickers"][m_ticker]
        
        # 2. DB 데이터로 메모리 업데이트 (기본값 유지 및 신규 추가)
        for ticker, t in db_tickers.items():
            name = t['name']
            
            # 종목명이 티커와 같거나 비어있으면 이름 찾기 시도
            if not name or name == ticker:
                resolved = self.resolve_ticker_name(ticker)
                if resolved != ticker:
                    name = resolved
                    self.db.add_ticker(ticker, name) # DB에도 업데이트
            
            if ticker not in self.data_store["tickers"]:
                buy_rule = t.get('buy_rule', 'DEFAULT')
                init_status = "중지됨 (전략없음)" if (not buy_rule or buy_rule == 'NONE') else "중지됨"
                self.data_store["tickers"][ticker] = {
                    "name": name,
                    "price": 0,
                    "status": init_status,
                    "buy_rule": buy_rule,
                    "position_qty": 0,
                    "avg_price": 0,
                    "realized_profit": 0,
                    "paused": not bool(t.get('is_active', 1))
                }
            else:
                # 기존 항목은 메타데이터(이름, 규칙, 일시정지여부)만 업데이트하여 런타임 데이터(가격 등) 보존
                self.data_store["tickers"][ticker].update({
                    "name": name,
                    "buy_rule": t.get('buy_rule', 'DEFAULT'),
                    "paused": not bool(t.get('is_active', 1))
                })

    def zmq_send(self, payload):
        """게이트웨이로 명령 전송 (스레드 안전)"""
        with self.zmq_send_lock:
            self.pub_socket.send_json(payload)

    def add_log(self, msg):
        self.logs.append(msg)
        # 무한 메모리 증가 방지: 최근 1000개만 유지
        if len(self.logs) > 1000:
            del self.logs[:-1000]
        print(f"[Engine] {msg}")

    def run_simulation(self, ticker, config, stop_event):
        """
        config: {start_price, duration, seed, scenario, mode, date}
        """
        mode = config.get('mode', 'GENERATION')
        name = self.data_store["tickers"][ticker].get("name", ticker)
        
        try:
            if mode == 'REPLAY':
                date_str = config.get('date')
                if not date_str:
                    self.add_log(f"시뮬레이션 오류: REPLAY 모드이나 날짜가 지정되지 않음 ({ticker})")
                    return
                
                self.add_log(f"시뮬레이션(재생) 시작: {name} ({date_str})")
                ticks = self.db.get_tick_data(ticker, date_str)
                if not ticks:
                    self.add_log(f"시뮬레이션 오류: {date_str} 에 해당하는 틱 데이터가 존재하지 않음 ({ticker})")
                    logging.error(f"No ticks found for {ticker} on {date_str}")
                    return
                
                total_ticks = len(ticks)
                self.add_log(f"틱 데이터 로드 완료: {total_ticks} 건")
                logging.info(f"Loaded {total_ticks} ticks for {ticker} replay")
                
                replay_speed = float(config.get('replay_speed', 0.05))  # 기본 0.05초/틱
                for idx, tick in enumerate(ticks):
                    if stop_event.is_set(): break
                    
                    price = float(tick['price'])
                    volume = int(tick['volume'])
                    scenario = tick.get('scenario', 'NONE')
                    
                    self.on_ticker_update(ticker, price, volume=volume, scenario=scenario)
                    self.data_store["tickers"][ticker]["price"] = price
                    
                    if idx % 100 == 0:
                        logging.info(f"Replay progress for {ticker}: {idx}/{total_ticks}")
                    
                    # REPLAY 속도 조절 (config에서 override 가능)
                    time.sleep(replay_speed)
            else:
                # 기존 GENERATION 모드
                from backend.simulator.generator import TickGenerator
                
                start_price = float(config.get('start_price', 100000))
                duration = int(config.get('duration', 3600))
                seed = config.get('seed')
                if seed is not None: seed = int(seed)
                initial_scenario = config.get('scenario', 'SIDEWAYS')
                
                self.add_log(f"시뮬레이션(생성) 시작: {name} ({initial_scenario}, 시작가:{start_price})")
                
                generator = TickGenerator(start_price=start_price, seed=seed, initial_scenario=initial_scenario)
                
                step = 0
                while step < duration and not stop_event.is_set():
                    df = generator.generate(duration_seconds=1)
                    if df.empty: break
                    
                    tick = df.iloc[0]
                    price = float(tick['price'])
                    volume = int(tick['volume'])
                    scenario = tick['scenario']
                    
                    self.on_ticker_update(ticker, price, volume=volume, scenario=scenario)
                    self.data_store["tickers"][ticker]["price"] = price
                    
                    time.sleep(1) 
                    step += 1
        except Exception as e:
            logging.error(f"Error in run_simulation for {ticker}: {str(e)}")
            self.add_log(f"시뮬레이션 실행 중 오류 발생: {ticker}")
        finally:
            self.add_log(f"시뮬레이션 종료: {name}")
            # 재시작 경쟁 방지: 내 stop_event일 때만 정리
            # (무조건 삭제하면 방금 시작된 새 시뮬레이션의 이벤트를 지워 중지 불가 상태가 됨)
            if self.simulation_stop_events.get(ticker) is stop_event:
                del self.simulation_stop_events[ticker]
                if ticker in self.data_store["tickers"]:
                    self.data_store["tickers"][ticker]["simulating"] = False

    def resolve_ticker_name(self, ticker):
        """티커를 기반으로 실제 종목명을 찾음 (DB 우선 조회)"""
        if not ticker: return ""
        
        # 0. 자주 쓰이는 주요 종목 하드코딩 (검색 엔진 부하 및 크래시 방지)
        presets = {
            "QQQ": "Invesco QQQ Trust",
            "SQQQ": "ProShares UltraPro Short QQQ",
            "TQQQ": "ProShares UltraPro QQQ",
            "PSQ": "ProShares Short QQQ",
            "AAPL": "Apple Inc.",
            "TSLA": "Tesla, Inc.",
            "MSFT": "Microsoft Corporation",
            "NVDA": "NVIDIA Corporation",
            "122630": "KODEX 레버리지",
            "252670": "KODEX 200선물인버스2X",
            "069500": "KODEX 200",
            "114800": "KODEX 인버스",
            "005930": "삼성전자",
            "000660": "SK하이닉스"
        }
        pure_ticker = ticker.split('.')[0].upper()
        if pure_ticker in presets:
            return presets[pure_ticker]

        try:
            # 1. DB에서 먼저 확인 (가장 빠름)
            conn = self.db.get_connection()
            try:
                with conn.cursor() as cur:
                    norm_ticker = self.db.normalize_ticker(ticker)
                    yf_ticker = self.db.to_yfinance_ticker(ticker)
                    
                    sql = "SELECT name FROM tickers WHERE ticker IN (%s, %s)"
                    cur.execute(sql, (norm_ticker, yf_ticker))
                    row = cur.fetchone()
                    if row and row['name'] and row['name'] != row['ticker']:
                        return row['name']
            finally:
                conn.close()

            # 2. 검색 서비스(Yahoo/KRX)를 통해 찾기
            yf_ticker = self.db.to_yfinance_ticker(ticker)
            search_res = self.collector.search_ticker(yf_ticker)
            if search_res:
                match = next((r for r in search_res if r['ticker'].upper() == yf_ticker.upper()), None)
                if not match:
                    match = next((r for r in search_res if r['ticker'].upper() == ticker.upper()), None)
                
                if match:
                    return match['name']
        except Exception as e:
            logging.error(f"Error resolving name for {ticker}: {e}")
        return ticker

    def add_ticker(self, ticker_input, rule='DEFAULT'):
        ticker = self.db.normalize_ticker(ticker_input)
        # 실제 종목명 검색 시도
        name = self.resolve_ticker_name(ticker)
        
        # DB에 추가
        self.db.add_ticker(ticker, name, "REAL", buy_rule=rule)
        self.load_tickers_from_db()
        
        # 로그 추가 (Discord 알림용)
        self.add_log(f"➕ 종목 추가: {name} ({ticker})")
        
        # 실시간 데이터 등록 요청 (Gateway)
        active_tickers = [t for t, d in self.data_store["tickers"].items() if not d.get("paused")]
        if active_tickers:
            self.zmq_send({"action": "SET_REAL", "tickers": ";".join(active_tickers)})
        return True

    def remove_ticker(self, ticker_input):
        ticker = self.db.normalize_ticker(ticker_input)
        name = ticker
        if ticker in self.data_store["tickers"]:
            name = self.data_store["tickers"][ticker].get("name", ticker)
            
        self.db.remove_ticker(ticker)
        if ticker in self.data_store["tickers"]:
            del self.data_store["tickers"][ticker]
            
        # 로그 추가 (Discord 알림용)
        self.add_log(f"🗑️ 종목 삭제: {name} ({ticker})")
        return True

    def set_rule(self, ticker_input, rule_name):
        ticker = self.db.normalize_ticker(ticker_input)
        res = self.db.update_ticker_rule(ticker, rule_name)
        if res:
            if ticker in self.data_store["tickers"]:
                self.data_store["tickers"][ticker]["buy_rule"] = rule_name
                self.data_store["tickers"][ticker]["paused"] = False
            self.strategy.clear_strategy_cache(rule_name)
        return res

    def pause_ticker(self, ticker_input):
        ticker = self.db.normalize_ticker(ticker_input)
        res = self.db.update_ticker_status(ticker, False)
        if res and ticker in self.data_store["tickers"]:
            self.data_store["tickers"][ticker]["paused"] = True
        return res

    def resume_ticker(self, ticker_input):
        ticker = self.db.normalize_ticker(ticker_input)
        res = self.db.update_ticker_status(ticker, True)
        if res and ticker in self.data_store["tickers"]:
            self.data_store["tickers"][ticker]["paused"] = False
        return res

engine_instance = None

@app.route('/login', methods=['POST'])
def login():
    mode = request.json.get('mode', 'REAL')
    asset_type = request.json.get('asset_type', 'STOCK')
    asset_label = '주식' if asset_type == 'STOCK' else '코인'
    
    if mode == 'VIRTUAL':
        engine_instance.status = f"CONNECTED (VIRTUAL/{asset_label})"
        
        # [핵심] 모드 전환 및 참조 업데이트
        engine_instance.current_mode = "VIRTUAL"
        engine_instance.data_store["account"] = engine_instance.accounts["VIRTUAL"]
        
        curr_acc = engine_instance.data_store["account"].get("acc_no", "")
        
        # 가상 모드 초기화 로직 (계좌번호가 가상 형식이 아니면 초기화)
        if not curr_acc.startswith("VIRTUAL"):
            engine_instance.data_store["account"].update({
                "acc_no": "VIRTUAL-001",
                "name": "가상 사용자",
                "balance": 100000000,
                "asset_type": asset_type,
                "mode": "VIRTUAL",
                "holdings": [],
                "acc_list": ["VIRTUAL-001"],
                "server": "가상"
            })
        else:

            # 이미 가상 모드인 경우: 필요한 값만 업데이트 (또는 유지)
            engine_instance.data_store["account"]["asset_type"] = asset_type
            engine_instance.data_store["account"]["mode"] = "VIRTUAL"
            engine_instance.data_store["account"]["server"] = "가상"
            
            if not engine_instance.data_store["account"].get("name"):
                engine_instance.data_store["account"]["name"] = "가상 사용자"
            if not engine_instance.data_store["account"].get("acc_no") or not engine_instance.data_store["account"]["acc_no"].startswith("VIRTUAL"):
                engine_instance.data_store["account"]["acc_no"] = "VIRTUAL-001"
            if engine_instance.data_store["account"].get("balance", 0) == 0:
                engine_instance.data_store["account"]["balance"] = 100000000
        
        # 자동 재연결을 위해 마지막 연결 정보 기록
        engine_instance.last_connection = {
            "mode": "VIRTUAL",
            "asset_type": asset_type,
            "broker": engine_instance.data_store["account"].get("broker", "KIWOOM")
        }
        # 변경사항 즉시 파일 저장
        engine_instance.save_account_config()
        
        # [추가] 가상 모드 연결 시에도 모든 전략 일시정지 처리
        engine_instance.db.deactivate_all_tickers()
        for t_key in engine_instance.data_store["tickers"]:
            engine_instance.data_store["tickers"][t_key]["paused"] = True
            # [추가] 상태 문자열 즉시 업데이트
            rule = engine_instance.data_store["tickers"][t_key].get("buy_rule", "DEFAULT")
            engine_instance.data_store["tickers"][t_key]["status"] = "중지됨 (전략없음)" if (not rule or rule == 'NONE') else "중지됨"
            
        engine_instance.add_log(f"가상 모드 로그인 성공 [{asset_label}] - 계정: {engine_instance.data_store['account']['name']}")
        return jsonify({"status": "CONNECTED", "message": f"가상 모드 연결됨 [{asset_label}]", "account": engine_instance.data_store["account"]})
    elif mode in ['REAL', 'MOCK']:
        if mode == 'MOCK':
            # ── 모의투자 가능 시간 확인 (평일 09:00 ~ 15:30 KST) ──
            import pytz
            KST = pytz.timezone("Asia/Seoul")
            now_kst = datetime.now(KST)
            START_TIME = now_kst.replace(hour=9,  minute=0,  second=0, microsecond=0)
            END_TIME   = now_kst.replace(hour=15, minute=30, second=0, microsecond=0)
            is_weekday  = now_kst.weekday() < 5  # 0=월 ~ 4=금
            is_in_time  = START_TIME <= now_kst <= END_TIME

            if asset_type != 'COIN' and (not is_weekday or not is_in_time):
                msg = (
                    f"현재 시간은 모의투자 가능 시간이 아닙니다.\n"
                    f"모의투자 서버는 평일 정규장(09:00 ~ 15:30)에 운영됩니다.\n"
                    f"(현재: {now_kst.strftime('%Y-%m-%d %H:%M')} KST)"
                )
                engine_instance.add_log(f"[모의투자] {msg}")
                return jsonify({"status": "TIME_ERROR", "message": msg}), 400

        # [핵심] 공통 로그인 시도 로직 (REAL/MOCK 모두 도달)
        engine_instance.status = "TRYING"
        engine_instance.current_mode = mode
        engine_instance.data_store["account"] = engine_instance.accounts[mode]
        
        engine_instance.data_store["account"]["asset_type"] = asset_type
        engine_instance.data_store["account"]["mode"] = mode
        
        label = '모의투자' if mode == 'MOCK' else '실전'
        broker = engine_instance.data_store["account"].get("broker", "KIWOOM")
        
        # [신규] 코인 자산 유형: 바이낸스 API 사용
        if asset_type == 'COIN':
            engine_instance.add_log(f"{label} 로그인 시도 [바이낸스 API / 코인]")
            
            bn_config = engine_instance.accounts.get("binance_config", {})
            market_type = bn_config.get("market_type", "FUTURES")
            is_testnet = bn_config.get("is_testnet", False) or (mode == "MOCK")

            if market_type == "SPOT":
                api_key = bn_config.get("spot_api_key")
                api_secret = bn_config.get("spot_api_secret")
            else:
                api_key = bn_config.get("futures_api_key")
                api_secret = bn_config.get("futures_api_secret")

            if not api_key or not api_secret:
                market_label = "현물(Spot)" if market_type == "SPOT" else "선물(Futures)"
                engine_instance.status = "ERROR: Binance API 설정 필요"
                engine_instance.add_log(f"바이낸스 {market_label} API Key/Secret이 설정되지 않았습니다. 환경설정에서 입력해주세요.")
                return jsonify({"status": "ERROR", "message": f"바이낸스 {market_label} API Key/Secret 미설정. 환경설정 → 바이낸스 설정에서 입력하세요."}), 400

            # [DEBUG] 바이낸스 연동 키 확인 (앞 4자, 뒤 4자)
            mask_key = f"{api_key[:4]}...{api_key[-4:]}" if api_key and len(api_key) > 8 else "너무 짧음"
            mask_secret = f"{api_secret[:4]}...{api_secret[-4:]}" if api_secret and len(api_secret) > 8 else "너무 짧음"
            engine_instance.add_log(f"[DEBUG] {market_type} 테스트넷={'예' if is_testnet else '아니오'}")
            engine_instance.add_log(f"[DEBUG] Key: {mask_key}, Secret: {mask_secret}")

            engine_instance.binance_broker = BinanceBroker(
                api_key=api_key,
                api_secret=api_secret,
                is_testnet=is_testnet,
                market_type=market_type
            )
            
            if engine_instance.binance_broker.auth():
                engine_instance.status = "CONNECTED"
                
                # 잔고 조회
                bn_data = engine_instance.binance_broker.get_balance()
                if bn_data:
                    engine_instance.data_store["account"]["balance"] = bn_data["balance"]
                    engine_instance.data_store["account"]["holdings"] = bn_data["holdings"]
                    engine_instance.data_store["account"]["acc_no"] = "BINANCE"
                
                testnet_label = "테스트넷" if is_testnet else "메인넷"
                engine_instance.data_store["account"]["server"] = f"바이낸스({testnet_label})"
                engine_instance.data_store["account"]["name"] = "바이낸스 사용자"
                engine_instance.data_store["account"]["broker"] = "BINANCE"
                engine_instance.data_store["account"]["acc_list"] = ["BINANCE"]
                
                # 연결 시 모든 전략 일시정지
                engine_instance.db.deactivate_all_tickers()
                for t_key in engine_instance.data_store["tickers"]:
                    engine_instance.data_store["tickers"][t_key]["paused"] = True
                    rule = engine_instance.data_store["tickers"][t_key].get("buy_rule", "DEFAULT")
                    engine_instance.data_store["tickers"][t_key]["status"] = "중지됨 (전략없음)" if (not rule or rule == 'NONE') else "중지됨"
                
                # 자동 재연결을 위해 마지막 연결 정보 기록
                engine_instance.last_connection = {
                    "mode": mode,
                    "asset_type": "COIN",
                    "broker": "BINANCE"
                }
                engine_instance.save_account_config()
                engine_instance.add_log(f"바이낸스 API 연결 성공 ({testnet_label})")
                return jsonify({"status": "CONNECTED", "message": f"바이낸스 {testnet_label} 연결 성공 [코인]"})
            else:
                engine_instance.status = "ERROR: Binance 인증 실패"
                engine_instance.add_log("바이낸스 API 인증 실패 (API Key/Secret 확인 필요)")
                return jsonify({"status": "ERROR", "message": "바이낸스 인증 실패"}), 401
        
        # [주식 자산 유형 처리]
        if broker == "KOREA_INVESTMENT":
            engine_instance.add_log(f"{label} 로그인 시도 [한국투자증권 API / 64-bit]")
            
            # KIS Broker 초기화 (저장된 설정 로드)
            is_mock_env = (mode == "MOCK")
            config = engine_instance.data_store["account"].get("kis_config", {})
            app_key = config.get("app_key")
            app_secret = config.get("app_secret")
            acc_no = config.get("acc_no") or engine_instance.data_store["account"].get("acc_no")
            
            # [수정] 하이픈이 없더라도 10자리 숫자이면 정상적인 KIS 계좌번호로 간주함
            is_valid_kis_format = acc_no and (("-" in str(acc_no) and len(str(acc_no)) >= 10) or (str(acc_no).isdigit() and len(str(acc_no)) == 10))
            
            if acc_no and not is_valid_kis_format:
                logging.info(f"Invalid KIS account format detected ({acc_no}), ignoring for auto-fetch.")
                acc_no = None

            engine_instance.kis_broker = KISBroker(
                key=app_key, 
                secret=app_secret, 
                acc_no=acc_no, 
                is_mock=is_mock_env
            )
            
            if engine_instance.kis_broker.auth():
                engine_instance.status = "CONNECTED"
                
                # 잔고 및 계좌 정보 즉시 동기화
                kis_data = engine_instance.kis_broker.get_balance()
                if kis_data:
                    engine_instance.data_store["account"]["balance"] = kis_data["balance"]
                    engine_instance.data_store["account"]["holdings"] = kis_data["holdings"]
                    # [수정] KIS에서 조회된 실제 계좌번호로 즉시 업데이트 (키움 잔재 제거)
                    if kis_data.get("acc_no"):
                        engine_instance.data_store["account"]["acc_no"] = kis_data["acc_no"]
                
                engine_instance.data_store["account"]["server"] = f"한국투자({'모의' if is_mock_env else '실전'}/64bit)"
                engine_instance.data_store["account"]["name"] = "한투 사용자"
                
                # [수정] 계좌번호가 없거나 한투 형식이 아니면(키움 번호 등) Broker 정보로 강제 업데이트
                curr_acc = engine_instance.data_store["account"].get("acc_no", "")
                if not curr_acc or "-" not in curr_acc:
                    engine_instance.data_store["account"]["acc_no"] = engine_instance.kis_broker.acc_no or "KIS-ACCOUNT"
                
                # 계좌 목록도 KIS 계좌로 업데이트
                engine_instance.data_store["account"]["acc_list"] = [engine_instance.data_store["account"]["acc_no"]]
                
                # 자동 재연결을 위해 마지막 연결 정보 기록
                engine_instance.last_connection = {
                    "mode": mode,
                    "asset_type": "STOCK",
                    "broker": "KOREA_INVESTMENT"
                }
                engine_instance.save_account_config()
                engine_instance.add_log(f"한국투자증권 API 연결 성공 ({'모의투자' if is_mock_env else '실전'})")
                return jsonify({"status": "CONNECTED", "message": f"{label} 로그인 성공 [한국투자증권 64-bit API]"})
            else:
                engine_instance.status = "ERROR: KIS 인증 실패"
                engine_instance.add_log("한국투자증권 API 인증 실패 (AppKey/Secret 확인 필요)")
                return jsonify({"status": "ERROR", "message": "KIS 인증 실패"}), 401
        else:
            engine_instance.add_log(f"{label} 로그인 시도 [{asset_label}]")
            engine_instance.zmq_send({"action": "LOGIN", "mode": mode, "asset_type": asset_type})
            return jsonify({"status": "TRYING", "message": f"{label} 로그인 시도 중... [{asset_label}]"})

def mask_account_info(acc_data):
    import copy
    d = copy.deepcopy(acc_data)
    
    # Handle both nested and flat structures for KIS config
    if "kis_config" in d and isinstance(d["kis_config"], dict):
        kis = d["kis_config"]
        # Check for nested REAL/MOCK structure
        for m in ["REAL", "MOCK"]:
            if m in kis and isinstance(kis[m], dict):
                for k in ["app_key", "app_secret"]:
                    if kis[m].get(k):
                        kis[m][k] = "*****"
        # Check for flat structure (current mode)
        for k in ["app_key", "app_secret"]:
            if kis.get(k):
                kis[k] = "*****"
                
    # Kiwoom 상세 설정 마스킹
    if "kiwoom_config" in d and isinstance(d["kiwoom_config"], dict):
        for k in ["user_id", "user_pw", "cert_pw"]:
            if d["kiwoom_config"].get(k):
                d["kiwoom_config"][k] = "*****"
                
    # Discord 상세 설정 마스킹
    if "discord_config" in d and isinstance(d["discord_config"], dict):
        for k in ["bot_token", "guild_id", "log_channel_id", "cmd_channel_id"]:
            if d["discord_config"].get(k):
                d["discord_config"][k] = "*****"
                
    return d

@app.route('/account', methods=['POST'])
def update_account():
    data = request.json
    engine_instance.update_account(data)
    masked_acc = mask_account_info(engine_instance.data_store["account"])
    return jsonify({"status": "SUCCESS", "account": masked_acc})

@app.route('/trades', methods=['GET'])
def get_trades():
    date_str = request.args.get('date') # YYYY-MM-DD
    acc_no = request.args.get('acc_no')
    if not date_str:
        date_str = datetime.now().strftime('%Y-%m-%d')
    trades = engine_instance.db.get_trades_by_date(date_str, acc_no=acc_no)
    return jsonify(trades)

@app.route('/trades/summary', methods=['GET'])
def get_trades_summary():
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    acc_no = request.args.get('acc_no')
    if not year or not month:
        now = datetime.now()
        year, month = now.year, now.month
    summary = engine_instance.db.get_monthly_trade_summary(year, month, acc_no=acc_no)

    # 정산 기준(opt10074) 일일 손익이 있으면 그 값으로 덮어씀 (키움 앱과 일치)
    totals = engine_instance.db.get_daily_profit_totals_by_month(year, month, acc_no=acc_no)
    for d, t in totals.items():
        if d in summary:
            summary[d]["profit"] = t["profit"]
        else:
            summary[d] = {"trade_count": 0, "profit": t["profit"], "amount": t.get("sell_amount", 0)}
    return jsonify(summary)

@app.route('/trades/export-gsheet', methods=['POST'])
def export_trades_gsheet():
    # 매매일지를 구글 스프레드시트에 업로드
    req = request.json or {}
    date_str = req.get('date')
    acc_no = req.get('acc_no')
    if not date_str:
        return jsonify({"status": "ERROR", "message": "date 누락"}), 400
    try:
        from core.service.gsheet_exporter import GSheetExporter, GSheetConfigError
        try:
            # 계좌가 '해외' 모드면 해외 주식용 스프레드시트로 업로드
            market = (engine_instance.data_store.get("account") or {}).get("market", "DOMESTIC")
            exporter = GSheetExporter(market=market)
            result = exporter.export_daily(engine_instance.db, date_str, acc_no=acc_no)
            market_label = "해외" if market == "OVERSEAS" else "국내"
            engine_instance.add_log(f"매매일지 구글 시트 업로드 완료 ({date_str}, {result['rows']}건, {market_label})")
            return jsonify({"status": "SUCCESS", **result})
        except GSheetConfigError as e:
            return jsonify({"status": "CONFIG_ERROR", "message": str(e)}), 400
    except Exception as e:
        logging.error(f"GSheet export error: {e}", exc_info=True)
        return jsonify({"status": "ERROR", "message": str(e)}), 500

@app.route('/account/refresh', methods=['POST'])
def refresh_account_info():
    # 보유 종목/잔고 새로고침 — 키움: REFRESH_ACCOUNT 요청 → 경량 LOGIN_RESULT로 갱신됨
    if engine_instance.status != "CONNECTED":
        return jsonify({"status": "ERROR",
                        "message": "계좌가 연결되어 있지 않습니다. 먼저 로그인하세요."}), 400
    account = engine_instance.data_store.get("account") or {}
    broker = account.get("broker", "KIWOOM")
    try:
        if broker == "KOREA_INVESTMENT" and engine_instance.kis_broker:
            kis_data = engine_instance.kis_broker.get_balance()
            if kis_data:
                account["balance"] = kis_data["balance"]
                account["holdings"] = kis_data["holdings"]
            return jsonify({"status": "SUCCESS", "message": "계좌 정보를 갱신했습니다."})
        engine_instance.zmq_send({
            "action": "REFRESH_ACCOUNT",
            "acc_no": account.get("acc_no"),
            "market": account.get("market", "DOMESTIC"),
        })
        # 게이트웨이 TR 조회 후 LOGIN_RESULT로 갱신되므로 수 초 뒤 /status에 반영된다
        return jsonify({"status": "TRYING", "message": "새로고침 요청을 보냈습니다."})
    except Exception as e:
        logging.error(f"Account refresh failed: {e}", exc_info=True)
        return jsonify({"status": "ERROR", "message": str(e)}), 500

@app.route('/holdings/export-gsheet', methods=['POST'])
def export_holdings_gsheet():
    # 현재 보유 종목을 구글 시트 '보유종목' 탭에 업로드
    account = engine_instance.data_store.get("account") or {}
    holdings = account.get("holdings")
    if not holdings:
        return jsonify({"status": "ERROR",
                        "message": "보유 중인 종목이 없습니다. 계좌 연결 후 다시 시도하세요."}), 400

    # AI 매매 전략 분석이 있으면 종목별로 함께 기록 (조회 실패가 업로드를 막지는 않도록)
    try:
        strategies = ai_trades.list_strategies()
    except Exception as e:
        logging.warning(f"AI 매매 전략 조회 실패 (보유종목 업로드는 계속): {e}")
        strategies = {}

    try:
        from core.service.gsheet_exporter import GSheetExporter, GSheetConfigError
        try:
            # 계좌가 '해외' 모드면 해외 주식용 스프레드시트로 업로드
            exporter = GSheetExporter(market=account.get("market", "DOMESTIC"))
            result = exporter.export_holdings(
                holdings,
                acc_no=account.get("acc_no"),
                snapshot_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                strategies=strategies)
            engine_instance.add_log(
                f"보유 종목 구글 시트 업로드 완료 ({result['rows']}종목)")
            return jsonify({"status": "SUCCESS", **result})
        except GSheetConfigError as e:
            return jsonify({"status": "CONFIG_ERROR", "message": str(e)}), 400
    except Exception as e:
        logging.error(f"Holdings gsheet export failed: {e}", exc_info=True)
        return jsonify({"status": "ERROR", "message": str(e)}), 500

@app.route('/trades/daily-total', methods=['GET'])
def get_trades_daily_total():
    # 정산 기준(opt10074) 일일 실현손익 조회
    date_str = request.args.get('date')
    acc_no = request.args.get('acc_no')
    if not date_str:
        date_str = datetime.now().strftime('%Y-%m-%d')
    total = engine_instance.db.get_daily_profit_total(date_str, acc_no=acc_no)
    if total:
        return jsonify({"exists": True, **total})
    return jsonify({"exists": False})

@app.route('/trades/sync', methods=['POST'])
def sync_trades():
    # Kiwoom 서버로부터 특정 날짜의 매매 내역을 가져와 DB에 저장함
    req_data = request.json
    date_str = req_data.get('date') # YYYY-MM-DD
    acc_no = req_data.get('acc_no')
    
    if not date_str or not acc_no:
        return jsonify({"status": "ERROR", "message": "Missing date or acc_no"}), 400
        
    # Gateway에 명령 전달
    engine_instance.zmq_send({
        "action": "SYNC_TRADES",
        "date": date_str,
        "acc_no": acc_no
    })
    
    return jsonify({"status": "SUCCESS", "message": f"Sync request sent for {date_str}"})

# ── 모바일 앱 APK 다운로드 (easy_project4 방식 참고) ──
def _apk_path():
    """trading_app 릴리스 APK 경로 (flutter build apk 산출물)"""
    return os.path.join(parent_dir, "trading_app", "build", "app",
                        "outputs", "flutter-apk", "app-release.apk")

@app.route('/apk/info', methods=['GET'])
def get_apk_info():
    # 모바일 앱 릴리스 APK 빌드 정보
    apk = _apk_path()
    if os.path.isfile(apk):
        st = os.stat(apk)
        return jsonify({
            "ok": True, "exists": True, "size": st.st_size,
            "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
        })
    return jsonify({"ok": True, "exists": False})

@app.route('/apk', methods=['GET'])
def download_apk():
    # 모바일 앱에서 최신 APK 다운로드 (앱 업데이트용)
    apk = _apk_path()
    if not os.path.isfile(apk):
        return jsonify({"ok": False,
                        "error": "APK 없음 — trading_app에서 flutter build apk로 생성하세요."}), 404
    return send_file(apk, mimetype="application/vnd.android.package-archive",
                     as_attachment=True, download_name="jbrain_trader.apk")

@app.route('/status', methods=['GET'])
def get_status():
    # 시뮬레이션/ZMQ 스레드가 dict에 키를 추가할 수 있으므로 스냅샷으로 순회
    # (순회 중 크기 변경 시 RuntimeError로 /status가 500 반환)
    for ticker in list(engine_instance.data_store["tickers"].keys()):
        ticker_data = engine_instance.data_store["tickers"].get(ticker)
        if ticker_data is None:
            continue
        ticker_data["details"] = engine_instance.strategy.get_status_details(ticker)
        ticker_data["analysis"] = engine_instance.strategy.get_analysis_data(ticker)
    
    status = engine_instance.status
    
    # 1. 현재 계정 정보 마스킹 (기본 정보)
    account_info = mask_account_info(engine_instance.data_store["account"])
    # 계좌별 시장 설정 (국내전용/해외전용 체크박스 표시용)
    account_info["acc_market_prefs"] = getattr(engine_instance, "acc_market_prefs", {})
    
    # 2. [핵심 수정보완] 
    # 프론트엔드 환경설정 페이지(SettingsPanel.vue)가 모든 설정을 한꺼번에 렌더링할 수 있도록 
    # kis_config, kiwoom_config, discord_config를 통합된 구조로 제공함.
    
    # (1) KIS 설정 통합 (REAL + MOCK)
    account_info["kis_config"] = {
        "REAL": mask_account_info({"kis_config": engine_instance.accounts.get("REAL", {}).get("kis_config", {})})["kis_config"],
        "MOCK": mask_account_info({"kis_config": engine_instance.accounts.get("MOCK", {}).get("kis_config", {})})["kis_config"]
    }
    
    # (2) Kiwoom 설정 보충
    if "kiwoom_config" not in account_info or not account_info["kiwoom_config"]:
        # 키움은 공용이므로 REAL 섹션에서 참조
        raw_kw = engine_instance.accounts.get("REAL", {}).get("kiwoom_config", {})
        account_info["kiwoom_config"] = mask_account_info({"kiwoom_config": raw_kw})["kiwoom_config"]
        
    # (3) Discord 설정 보충
    if "discord_config" not in account_info:
        raw_dc = engine_instance.accounts.get("discord_config", {})
        account_info["discord_config"] = mask_account_info({"discord_config": raw_dc})["discord_config"]
    
    # (4) Binance 설정 보충
    raw_bn = engine_instance.accounts.get("binance_config", {})
    account_info["binance_config"] = {
        "futures_api_key": "*****" if raw_bn.get("futures_api_key") else "",
        "futures_api_secret": "*****" if raw_bn.get("futures_api_secret") else "",
        "spot_api_key": "*****" if raw_bn.get("spot_api_key") else "",
        "spot_api_secret": "*****" if raw_bn.get("spot_api_secret") else "",
        "is_testnet": raw_bn.get("is_testnet", False),
        "market_type": raw_bn.get("market_type", "FUTURES")
    }
        
    return jsonify({
        "status": status,
        "account": account_info,
        "tickers": engine_instance.data_store["tickers"],
        "logs": engine_instance.logs[-50:]
    })
@app.route('/simulation/start', methods=['POST'])
def start_simulation():
    ticker_input = request.json.get('ticker')
    ticker = engine_instance.db.normalize_ticker(ticker_input)
    config = request.json.get('config', {})
    strategy_name = config.get('strategy')
    
    logging.info(f"Simulation start request for {ticker} with config: {config}")
    
    # 1. Ticker data_store 초기화/업데이트
    if ticker not in engine_instance.data_store["tickers"]:
        name = engine_instance.resolve_ticker_name(ticker)
        engine_instance.data_store["tickers"][ticker] = {
            "name": name, "price": 0, "status": "시뮬레이션 준비",
            "buy_rule": strategy_name, "position_qty": 0, "avg_price": 0,
            "realized_profit": 0, "paused": False
        }
    else:
        engine_instance.data_store["tickers"][ticker]["buy_rule"] = strategy_name
    
    # ★ 시뮬레이션 시작 시 항상 paused 해제 및 상태 초기화 (핵심 수정)
    engine_instance.data_store["tickers"][ticker]["paused"] = False
    engine_instance.data_store["tickers"][ticker]["status"] = "시뮬레이션 준비"
    engine_instance.data_store["tickers"][ticker]["position_qty"] = 0
    engine_instance.data_store["tickers"][ticker]["avg_price"] = 0
    engine_instance.data_store["tickers"][ticker]["realized_profit"] = 0
    # 포지션도 초기화
    if hasattr(engine_instance, 'strategy') and engine_instance.strategy:
        engine_instance.strategy.positions[ticker] = []
    

    engine_instance.data_store["tickers"][ticker]["slippage_enabled"] = config.get("slippage_enabled", False)
    engine_instance.data_store["tickers"][ticker]["slippage_rate"] = float(config.get("slippage_rate_pct", 0.05)) / 100.0

    # 2. 이미 실행 중인 시뮬레이션이 있다면 강제 중지 및 대기
    if ticker in engine_instance.simulation_stop_events:
        logging.info(f"Forcing reset of existing simulation for {ticker}")
        engine_instance.simulation_stop_events[ticker].set()
        # 이전 스레드가 완전히 종료될 때까지 잠시 대기
        time.sleep(0.5)
        if ticker in engine_instance.simulation_stop_events:
            del engine_instance.simulation_stop_events[ticker]

    # 3. 새로운 시뮬레이션 시작
    stop_event = threading.Event()
    engine_instance.simulation_stop_events[ticker] = stop_event
    threading.Thread(target=engine_instance.run_simulation, args=(ticker, config, stop_event), daemon=True).start()
    engine_instance.data_store["tickers"][ticker]["simulating"] = True
    
    logging.info(f"Simulation thread started/reset for {ticker}")
    return jsonify({"status": "STARTED"})

@app.route('/simulation/analyze', methods=['POST'])
def analyze_simulation():
    try:
        ticker_input = request.json.get('ticker', '005930')
        ticker_name = engine_instance.db.normalize_ticker(ticker_input)
        config = request.json.get('config', {})
        
        from backend.simulator.generator import TickGenerator
        
        start_price = float(config.get('start_price', 100000))
        duration = int(config.get('duration', 3600))
        seed = config.get('seed')
        if seed is not None: seed = int(seed)
        initial_scenario = config.get('scenario', 'SIDEWAYS')
        mode = config.get('mode', 'GENERATION')
        
        # Support multiple strategies
        strategies = config.get('strategies', [])
        if not strategies:
            # Fallback to single strategy if provided, else DEFAULT
            strategy_name = config.get('strategy', 'DEFAULT')
            strategies = [strategy_name]
            
        logging.info(f"Analysis request for {ticker_name} (Input:{ticker_input}, Mode:{mode}) with strategies {strategies}")
        broadcast_analysis_status(f"분석 시작: {ticker_name}")
        
        # 1. 시세 데이터 확보 (생성 또는 DB 조회)
        if mode == 'REPLAY':
            date_str = config.get('date')
            broadcast_analysis_status(f"DB에서 {ticker_name} 종목의 '{date_str}' 틱 데이터 로드 중...")
            df = engine_instance.db.get_tick_data_df(ticker_name, date_str)
            if df.empty:
                raise Exception(f"'{ticker_name}' 종목의 '{date_str}' 에 해당하는 틱 데이터가 DB에 없습니다.")
            broadcast_analysis_status(f"데이터 로드 완료: {len(df)} 틱 (DB)")
        else:
            broadcast_analysis_status("가상 시세 데이터 생성 중...")
            generator = TickGenerator(start_price=start_price, seed=seed, initial_scenario=initial_scenario)
            df = generator.generate(duration_seconds=duration)
            broadcast_analysis_status(f"데이터 생성 완료: {len(df)} 틱 (생성)")
        
        # 2. Backtrader 연동 분석 (각 전략별로 수행)
        from backend.simulator.datafeed import prepare_bt_dataframe, CustomPandasData
        from backend.simulator.strategy import ScenarioAwareStrategy 
        import backtrader as bt
        
        bt_df = prepare_bt_dataframe(df.copy())
        
        # 미국 주식 여부 판별 (숫자로만 구성 = 한국, 그 외 = 미국)
        is_us = not str(ticker_name).split('.')[0].isdigit()
        start_cash = 100000.0 if is_us else 10000000.0
        
        results = {} # {strategy_name: {summary, trade_history, pnl_history}}

        for idx, s_name in enumerate(strategies):
            broadcast_analysis_status(f"[{idx+1}/{len(strategies)}] '{s_name}' 전략 분석 중...")
            cerebro = bt.Cerebro(stdstats=False) # 표준 관찰자 비활성화로 속도 향상
            # Slippage 적용
            if config.get("slippage_enabled"):
                s_rate = float(config.get("slippage_rate_pct", 0.05)) / 100.0
                cerebro.broker.set_slippage_perc(s_rate)
                logging.info(f"Analysis with Slippage enabled: {s_rate}")
            
            # Pass strategy_name and ticker_name to ScenarioAwareStrategy
            cerebro.addstrategy(ScenarioAwareStrategy, strategy_name=s_name, ticker_name=ticker_name, printlog=False) 
            
            data = CustomPandasData(dataname=bt_df)
            cerebro.adddata(data)
            
            cerebro.broker.setcash(start_cash)
            
            # Kiwoom Commission Logic (한국 주식)
            class KiwoomCommInfo(bt.CommInfoBase):
                params = (
                    ('stocklike', True),
                    ('commtype', bt.CommInfoBase.COMM_PERC),
                    ('commission', 0.00015), # 0.015%
                    ('tax', 0.002),          # 0.2%
                )
                def _getcommission(self, size, price, pseudoexec):
                    if size > 0: # Buy
                        return size * price * self.p.commission
                    # Sell
                    return abs(size) * price * (self.p.commission + self.p.tax)

            # US Stock Commission Logic (미국 주식 - 한국투자증권 기준)
            class USStockCommInfo(bt.CommInfoBase):
                params = (
                    ('stocklike', True),
                    ('commtype', bt.CommInfoBase.COMM_PERC),
                    ('commission', 0.0025),      # 한투 온라인 수수료 0.25% (매수/매도 동일)
                    ('sec_fee_rate', 0.0000278),  # SEC Fee: 매도 대금의 0.00278%
                    ('taf_per_share', 0.000166),  # TAF: 주당 $0.000166
                    ('taf_max', 8.30),            # TAF 최대 $8.30
                )
                def _getcommission(self, size, price, pseudoexec):
                    qty = abs(size)
                    total = qty * price
                    kis_fee = total * self.p.commission
                    if size > 0:  # Buy
                        return kis_fee
                    # Sell: 한투 수수료 + SEC Fee + TAF
                    sec_fee = total * self.p.sec_fee_rate
                    taf = min(qty * self.p.taf_per_share, self.p.taf_max)
                    return kis_fee + sec_fee + taf

            if is_us:
                cerebro.broker.addcommissioninfo(USStockCommInfo())
                logging.info(f"US Stock commission applied for {ticker_name}")
            else:
                cerebro.broker.addcommissioninfo(KiwoomCommInfo()) 
            
            cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
            cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='tradeanalyzer')
            cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
            
            strats = cerebro.run()
            res = strats[0]
            
            final_value = cerebro.broker.getvalue()
            dd_analysis = res.analyzers.drawdown.get_analysis()
            max_dd = dd_analysis['max']['drawdown'] if 'max' in dd_analysis and 'drawdown' in dd_analysis['max'] else 0
            
            ta_analysis = {}
            try:
                ta = res.analyzers.tradeanalyzer.get_analysis()
                ta_analysis['total_trades'] = ta.total.total if 'total' in ta else 0
                ta_analysis['net_pnl'] = ta.pnl.net.total if 'pnl' in ta else 0
                ta_analysis['gross_pnl'] = ta.pnl.gross.total if 'pnl' in ta else 0
                ta_analysis['total_fees'] = ta_analysis['gross_pnl'] - ta_analysis['net_pnl']
            except: 
                ta_analysis['total_trades'] = 0
                ta_analysis['net_pnl'] = 0
                ta_analysis['gross_pnl'] = 0
                ta_analysis['total_fees'] = 0

            # REPLAY 모드는 config의 start_price가 아닌 실제 데이터의 시작가 기준으로 계산
            # (기본값 100000을 그대로 쓰면 profit_rate가 전혀 다른 값으로 저장됨)
            actual_start_price = float(df.iloc[0]['price']) if len(df) > 0 else start_price
            results[s_name] = {
                "summary": {
                    "total_ticks": len(df),
                    "start_price": actual_start_price,
                    "end_price": float(df.iloc[-1]['price']),
                    "profit_rate": float((df.iloc[-1]['price'] / actual_start_price - 1) * 100),
                    "portfolio_return": float((final_value / start_cash - 1) * 100),
                    "final_value": final_value,
                    "max_drawdown": float(max_dd),
                    "total_trades": ta_analysis['total_trades'],
                    "gross_pnl": float(ta_analysis['gross_pnl']),
                    "realized_pnl": float(ta_analysis['net_pnl']),
                    "total_fees": float(ta_analysis['total_fees'])
                },
                "trade_history": res.trade_history,
                "pnl_history": res.pnl_history
            }
            # Concise result summary to console
            profit_rate = results[s_name]["summary"]["portfolio_return"]
            logging.info(f"[Backtest Result] Ticker: {ticker_name}, Strategy: {s_name}, Trades: {ta_analysis['total_trades']}, Profit: {profit_rate:.2f}%")
            broadcast_analysis_status(f"'{s_name}' 분석 완료 ({ta_analysis['total_trades']}회 매매)")

        # 3. 프런트엔드 시각화용 데이터 구성
        # 가격 정보와 시나리오 정보가 포함된 기본 데이터 (전략 무관)
        base_chart_data = []
        for _, row in df.iterrows():
            base_chart_data.append({
                "time": int(row['ts'].timestamp()) * 1000,
                "value": row['price'],
                "volume": row['volume'],
                "scenario": row['scenario']
            })

        # 4. 결과 자동 저장 (DB)
        if mode == 'REPLAY':
            data_date = config.get('date', 'UNKNOWN')
            for s_name, res in results.items():
                summary = res["summary"]
                full_payload = {
                    "status": "SUCCESS",
                    "summaries": {s_name: summary},
                    "comparisons": {s_name: res["pnl_history"]},
                    "details": {s_name: res["trade_history"]},
                    "base_chart": base_chart_data,
                    "config": config
                }
                engine_instance.db.save_backtest_result(
                    ticker=ticker_name,
                    strategy_name=s_name,
                    data_date=data_date,
                    profit_rate=summary["portfolio_return"],
                    total_trades=summary["total_trades"],
                    max_dd=summary["max_drawdown"],
                    result_data_json=json.dumps(full_payload)
                )
            logging.info(f"Auto-saved {len(results)} backtest results to DB.")

        return jsonify({
            "status": "SUCCESS",
            "summaries": {name: res["summary"] for name, res in results.items()},
            "comparisons": {name: res["pnl_history"] for name, res in results.items()},
            "details": {name: res["trade_history"] for name, res in results.items()},
            "base_chart": base_chart_data,
            "config": config # Include config info for frontend
        })
    except Exception as e:
        import traceback
        err_msg = f"Error in analyze_simulation: {e}\n{traceback.format_exc()}"
        logging.error(err_msg)
        with open("analysis_error.log", "a", encoding='utf-8') as f:
            f.write(f"\n[{datetime.now()}] {err_msg}\n")
        return jsonify({"status": "ERROR", "message": str(e)}), 500

@app.route('/simulation/stop', methods=['POST'])
def stop_simulation():
    ticker_raw = request.json.get('ticker')
    ticker = engine_instance.db.normalize_ticker(ticker_raw) if engine_instance else ticker_raw
    if ticker in engine_instance.simulation_stop_events:
        engine_instance.simulation_stop_events[ticker].set()
        del engine_instance.simulation_stop_events[ticker]
        engine_instance.data_store["tickers"][ticker]["simulating"] = False
        return jsonify({"status": "STOPPED"})
    # Also try with raw ticker
    if ticker_raw in engine_instance.simulation_stop_events:
        engine_instance.simulation_stop_events[ticker_raw].set()
        del engine_instance.simulation_stop_events[ticker_raw]
        return jsonify({"status": "STOPPED"})
    return jsonify({"status": "NOT_RUNNING"})

@app.route('/debug/tick_history/<path:ticker>', methods=['GET'])
def debug_tick_history(ticker):
    """디버그용: 현재 tick_history에 저장된 데이터 확인"""
    try:
        norm = engine_instance.db.normalize_ticker(ticker) if engine_instance else ticker
        h1 = tick_history.get(norm, [])
        h2 = tick_history.get(ticker, [])
        return jsonify({
            "ticker_raw": ticker,
            "ticker_normalized": norm,
            "history_len_normalized": len(h1),
            "history_len_raw": len(h2),
            "all_keys": list(tick_history.keys()),
            "ws_clients_keys": list(ws_clients.keys()),
            "ws_loop_active": ws_loop is not None,
            "last_5": h1[-5:] if h1 else h2[-5:]
        })
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/debug/ws_clients', methods=['GET'])
def debug_ws_clients():
    """디버그용: WebSocket 구독자 목록 확인"""
    return jsonify({
        "ws_clients": {k: len(v) for k, v in ws_clients.items()},
        "global_ws_clients": len(global_ws_clients),
        "tick_history_keys": list(tick_history.keys()),
        "tick_history_sizes": {k: len(v) for k, v in tick_history.items()},
        "ws_loop_active": ws_loop is not None
    })


# --- 백테스트 결과 관리 API ---
@app.route('/backtest/results', methods=['GET'])
def get_backtest_results():
    limit = int(request.args.get('limit', 100))
    results = engine_instance.db.get_backtest_results(limit)
    
    # JSON 직렬화를 위해 Decimal -> float, datetime -> str 변환
    import decimal
    for r in results:
        if 'executed_at' in r and r['executed_at']:
            r['executed_at'] = r['executed_at'].strftime("%Y-%m-%d %H:%M:%S")
        if 'profit_rate' in r and isinstance(r['profit_rate'], decimal.Decimal):
            r['profit_rate'] = float(r['profit_rate'])
        if 'max_dd' in r and isinstance(r['max_dd'], decimal.Decimal):
            r['max_dd'] = float(r['max_dd'])
            
    return jsonify(results)

@app.route('/backtest/results/<int:result_id>', methods=['GET'])
def get_backtest_result_detail(result_id):
    detail_json = engine_instance.db.get_backtest_result_detail(result_id)
    if detail_json:
        return jsonify(json.loads(detail_json))
    return jsonify({"status": "ERROR", "message": "Result not found"}), 404

@app.route('/backtest/results/<int:result_id>', methods=['DELETE'])
def delete_backtest_result(result_id):
    if engine_instance.db.delete_backtest_result(result_id):
        return jsonify({"status": "SUCCESS"})
    return jsonify({"status": "ERROR"}), 500

# --- 전략 관리 API ---
@app.route('/strategies', methods=['GET'])
def get_strategies():
    strats = engine_instance.strategy_mgr.get_strategies()
    # datetime 객체는 JSON 직렬화가 안되므로 문자열로 변환
    for s in strats:
        if 'updated_at' in s:
            s['updated_at'] = s['updated_at'].strftime("%Y-%m-%d %H:%M:%S")
    return jsonify(strats)

@app.route('/strategies', methods=['POST'])
def save_strategy_route():
    name = request.json.get('name')
    content = request.json.get('content')
    if engine_instance.strategy_mgr.save_strategy(name, content):
        engine_instance.strategy.clear_strategy_cache(name)
        return jsonify({"status": "SUCCESS"})
    return jsonify({"status": "ERROR"})

@app.route('/strategies/<name>', methods=['DELETE'])
def delete_strategy_route(name):
    if engine_instance.strategy_mgr.delete_strategy(name):
        engine_instance.strategy.clear_strategy_cache(name)
        return jsonify({"status": "SUCCESS"})
    return jsonify({"status": "ERROR"})

# --- 종목 관리 API ---
@app.route('/add_ticker', methods=['POST'])
def add_ticker_route():
    ticker = request.json.get('ticker')
    rule = request.json.get('buy_rule', 'DEFAULT')
    engine_instance.add_ticker(ticker, rule)
    return jsonify({"status": "SUCCESS"})

@app.route('/remove_ticker', methods=['POST'])
def remove_ticker_route():
    ticker = request.json.get('ticker')
    engine_instance.remove_ticker(ticker)
    return jsonify({"status": "SUCCESS"})

@app.route('/set_rule', methods=['POST'])
def set_rule_route():
    ticker = request.json.get('ticker')
    rule_name = request.json.get('rule_name')
    if engine_instance.set_rule(ticker, rule_name):
        return jsonify({"status": "SUCCESS"})
    return jsonify({"status": "ERROR"})

@app.route('/pause_ticker', methods=['POST'])
def pause_ticker_route():
    ticker = request.json.get('ticker')
    if engine_instance.pause_ticker(ticker):
        return jsonify({"status": "SUCCESS"})
    return jsonify({"status": "ERROR"})

@app.route('/resume_ticker', methods=['POST'])
def resume_ticker_route():
    ticker = request.json.get('ticker')
    if engine_instance.resume_ticker(ticker):
        return jsonify({"status": "SUCCESS"})
    return jsonify({"status": "ERROR"})

# --- Flutter REST API 호환 라우트 ---
@app.route('/tickers', methods=['POST'])
def rest_add_ticker():
    """Flutter: POST /tickers {ticker, rule}"""
    ticker = request.json.get('ticker')
    rule = request.json.get('rule', 'DEFAULT')
    engine_instance.add_ticker(ticker, rule)
    return jsonify({"status": "SUCCESS"})

@app.route('/tickers/<ticker>', methods=['DELETE', 'OPTIONS'])
def rest_remove_ticker(ticker):
    """Flutter: DELETE /tickers/<ticker>"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    engine_instance.remove_ticker(ticker)
    return jsonify({"status": "SUCCESS"})

@app.route('/tickers/<ticker>/rule', methods=['POST', 'OPTIONS'])
def rest_set_rule(ticker):
    """Flutter: POST /tickers/<ticker>/rule {rule}"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    rule = request.json.get('rule', 'DEFAULT')
    if engine_instance.set_rule(ticker, rule):
        return jsonify({"status": "SUCCESS"})
    return jsonify({"status": "ERROR"})

@app.route('/tickers/<ticker>/pause', methods=['POST', 'OPTIONS'])
def rest_pause_ticker(ticker):
    """Flutter: POST /tickers/<ticker>/pause"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    if engine_instance.pause_ticker(ticker):
        return jsonify({"status": "SUCCESS"})
    return jsonify({"status": "ERROR"})

@app.route('/tickers/<ticker>/resume', methods=['POST', 'OPTIONS'])
def rest_resume_ticker(ticker):
    """Flutter: POST /tickers/<ticker>/resume"""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    if engine_instance.resume_ticker(ticker):
        return jsonify({"status": "SUCCESS"})
    return jsonify({"status": "ERROR"})

# --- 데이터 수집기 API ---
@app.route('/collector/start', methods=['POST'])
def start_collector():
    data = request.json
    tickers = data.get('tickers', [])
    interval = data.get('interval', '일봉')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    source = data.get('source', 'Yahoo')
    
    if not tickers:
        return jsonify({"status": "ERROR", "message": "종목을 선택해주세요."})
    
    engine_instance.collector.run_collection(tickers, interval, start_date, end_date, source)
    return jsonify({"status": "SUCCESS"})

@app.route('/collector/stop', methods=['POST'])
def stop_collector():
    engine_instance.collector.stop()
    return jsonify({"status": "SUCCESS"})

@app.route('/collector/search', methods=['GET'])
def search_collector_ticker():
    query = request.args.get('q', '')
    source = request.args.get('source', 'KRX')
    if not query:
        return jsonify([])
    
    results = engine_instance.collector.search_ticker(query, source)
    return jsonify(results)

@app.route('/collector/status', methods=['GET'])
def get_collector_status():
    return jsonify({
        "is_running": engine_instance.collector.is_running,
        "progress": engine_instance.collector.progress,
        "logs": engine_instance.collector.logs[-100:] # 최근 100개 로그만
    })

@app.route('/collector/date_status', methods=['GET'])
def get_collector_date_status():
    ticker_raw = request.args.get('ticker')
    is_all = ticker_raw == 'ALL'
    ticker = engine_instance.db.normalize_ticker(ticker_raw)
    interval = request.args.get('interval', '일봉')
    year = int(request.args.get('year', datetime.now().year))
    month = int(request.args.get('month', datetime.now().month))
    source = request.args.get('source', 'Yahoo')

    if not ticker_raw:
        return jsonify({"status": "ERROR", "message": "Ticker is required"}), 400

    # 해당 월의 시작일과 종료일 계산
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month:02d}-{last_day}"

    # 1. DB에서 수집 완료된 날짜 조회
    if is_all:
        collected_map = engine_instance.db.get_collected_dates_with_tickers(interval, start_date, end_date)
        generated_map = engine_instance.db.get_tick_generated_dates_with_tickers(start_date, end_date)
        
        # 종목명 맵핑 정보 (UI 표시용)
        ticker_names = {}
        # 1. DB tickers 테이블 매핑 (가장 빠르고 확실한 로컬 데이터)
        try:
            for t in engine_instance.db.get_tickers():
                name = t.get('name')
                raw_ticker = t.get('ticker')
                if name and raw_ticker:
                    ticker_names[raw_ticker] = name
                    norm_ticker = engine_instance.db.normalize_ticker(raw_ticker)
                    ticker_names[norm_ticker] = name
        except Exception as de:
            logging.error(f"DB ticker map load failed: {de}")

        # 2. KRX 캐시 보완 (외부 라이브러리 pykrx 연동 - 불안정하므로 완벽 격리)
        try:
            krx_provider = getattr(engine_instance.collector, 'krx', None)
            if krx_provider:
                # 캐시가 비어있어도 여기서 강제 로드하지 않음 (로드 실패 시 API가 대기하게 됨)
                # 대신 현재 가지고 있는 캐시만 안전하게 가져옴
                krx_map = engine_instance.collector.get_ticker_name_map_safe()
                if krx_map:
                    for k, v in krx_map.items():
                        if k not in ticker_names: # DB 데이터가 우선
                            ticker_names[k] = v
        except Exception as e:
            logging.warning(f"Fallback to KRX map failed: {e}")
    else:
        # 단일 종목 처리 로직... (생략됨)
        collected_dates = engine_instance.db.get_collected_dates(ticker, interval, start_date, end_date)
        generated_dates = engine_instance.db.get_tick_generated_dates(ticker, start_date, end_date)
        ticker_names = {}
    
    # 2. 날짜별 상태 매핑 시작
    now = datetime.now()
    status_map = {}
    
    for day in range(1, last_day + 1):
        dt = datetime(year, month, day)
        date_str = dt.strftime("%Y-%m-%d")
        
        # 기본값: NO_DATA (Grey)
        status = "NO_DATA"
        day_tickers = []
        
        # 주말인 경우 NO_DATA
        if dt.weekday() >= 5:
            status = "NO_DATA"
        else:
            # 주중인 경우 Yahoo 범위 체크
            days_diff = (now - dt).days
            
            can_fetch = False
            if source == "Yahoo":
                db_interval = engine_instance.db.map_interval(interval)
                if db_interval == "1m" or db_interval == "tick":
                    if 0 <= days_diff <= 7: can_fetch = True
                elif db_interval == "5m":
                    if 0 <= days_diff <= 60: can_fetch = True
                else: # 1d 등
                    if days_diff >= 0: can_fetch = True
            
            if can_fetch:
                status = "AVAILABLE" # White
            else:
                status = "NO_DATA" # Grey
        
        if is_all:
            # '전체' 보기인 경우 여러 종목의 상태 합침
            combined_tickers = []
            if date_str in collected_map:
                status = "COLLECTED"
                combined_tickers.extend(collected_map[date_str])
            if date_str in generated_map:
                status = "TICK_GENERATED" # 우선순위 높음
                for t in generated_map[date_str]:
                    if t not in combined_tickers: combined_tickers.append(t)
            
            # 종목코드를 이름으로 변환 (이름이 없으면 코드 그대로) 및 중복 제거
            day_labels = []
            for t in combined_tickers:
                # 1. 직접 매핑 확인
                name = ticker_names.get(t)
                if not name:
                    # 2. 정규화 (.KS 추가 등) 후 확인
                    norm_t = engine_instance.db.normalize_ticker(t)
                    name = ticker_names.get(norm_t)
                
                # 3. 매핑 실패 시 .KS 제거한 티커라도 사용
                label = name if name else t.split('.')[0]
                day_labels.append(label)
            
            day_tickers = sorted(list(set(day_labels)))
        else:
            # 단일 종목
            if date_str in collected_dates:
                status = "COLLECTED"
            if date_str in generated_dates:
                status = "TICK_GENERATED"
        
        if is_all:
            status_map[date_str] = {"status": status, "tickers": day_tickers}
        else:
            status_map[date_str] = status
            
    return jsonify({
        "ticker": ticker_raw,
        "interval": interval,
        "month_status": status_map
    })

@app.route('/collector/preview/<ticker>', methods=['GET'])
def get_collector_preview(ticker):
    interval = request.args.get('interval', '일봉')
    target_date = request.args.get('date') # YYYY-MM-DD
    
    # 티커 정규화
    ticker = engine_instance.db.normalize_ticker(ticker)
    
    # UI 인터벌 -> DB 인터벌 변환
    db_interval = engine_instance.db.map_interval(interval)
    
    # 0. Check if Tick data is requested
    if db_interval == "tick":
        history = tick_history.get(ticker, [])
        filtered = []
        
        if target_date:
            # 1. Try to find in memory first
            # [중요] 타임스탬프 계산 시 시장의 시간대를 고려해야 함
            is_us = not ticker.split('.')[0].isdigit()
            tz_market = pytz.timezone("America/New_York") if is_us else pytz.timezone("Asia/Seoul")

            filtered = [
                t for t in history 
                if datetime.fromtimestamp(t['time']/1000, tz_market).strftime("%Y-%m-%d") == target_date
            ]
            
            # 2. If not found in memory, fallback to DB Specifically for this date
            if not filtered:
                logging.info(f"Tick data for {ticker} on {target_date} not in memory. Querying DB...")
                rows = engine_instance.db.get_tick_data(ticker, target_date)
                if rows:
                    for row in rows:
                        dt = row['datetime']
                        if dt.tzinfo is None:
                            dt = tz_market.localize(dt)
                        filtered.append({
                            "time": int(dt.timestamp() * 1000),
                            "datetime": dt.strftime("%Y-%m-%d %H:%M:%S") if dt.tzinfo else row['datetime'].strftime("%Y-%m-%d %H:%M:%S"),
                            "value": float(row['price']),
                            "volume": int(row['volume']),
                            "scenario": row.get('scenario', 'NONE')
                        })
        else:
            # 1. If no target_date, use memory history
            filtered = history
            
            # 2. If memory is empty, fallback to latest 500 from DB
            if not filtered:
                logging.info(f"No tick history in memory for {ticker}. Fetching latest 500 from DB...")
                rows = engine_instance.db.get_tick_data(ticker, limit=500)
                is_us = not ticker.split('.')[0].isdigit()
                tz_market = pytz.timezone("America/New_York") if is_us else pytz.timezone("Asia/Seoul")
                
                filtered = []
                for row in rows:
                    dt = row['datetime']
                    if dt.tzinfo is None:
                        dt = tz_market.localize(dt)
                    filtered.append({
                        "time": int(dt.timestamp() * 1000),
                        "datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "value": float(row['price']),
                        "volume": int(row['volume']),
                        "scenario": row.get('scenario', 'NONE')
                    })
                filtered.sort(key=lambda x: x['time'])
            
        formatted_data = []
        for row in filtered:
            formatted_data.append({
                "time": row['time'],
                "datetime": row.get('datetime') or datetime.fromtimestamp(row['time']/1000).strftime("%Y-%m-%d %H:%M:%S"),
                "open": float(row['value']),
                "high": float(row['value']),
                "low": float(row['value']),
                "close": float(row['value']),
                "value": float(row['value']),
                "volume": int(row.get('volume', 0)),
                "scenario": row.get('scenario', 'NONE')
            })
        return jsonify(formatted_data)

    # 1. 데이터 조회
    if target_date and interval != "일봉":
        # 특정 날짜 데이터 전체 조회 (분봉용)
        try:
            conn = engine_instance.db.get_connection()
            try:
                with conn.cursor() as cur:
                    # 주기별 테이블 이름 가져오기
                    table_name = engine_instance.db._get_ohlcv_table(db_interval)
                    sql = f"""
                        SELECT datetime, open, high, low, close, volume 
                        FROM {table_name}
                        WHERE ticker = %s
                        AND DATE(datetime) = %s
                        ORDER BY datetime ASC
                    """
                    cur.execute(sql, (ticker, target_date))
                    data = cur.fetchall()
            finally:
                conn.close()
        except Exception as e:
            logging.error(f"Error fetching specific date data: {e}")
            data = []
    else:
        # 최신 500건 조회 (일봉 또는 날짜 미지정 시)
        data = engine_instance.db.get_ohlcv_data(ticker, db_interval, limit=500)
    
    # DB 결과가 튜플일 수 있으므로 정렬 시 sorted() 사용
    if data:
        data = sorted(data, key=lambda x: x['datetime'])
    
    # JSON 직렬화
    formatted_data = []
    for row in data:
        formatted_data.append({
            "time": int(row['datetime'].timestamp() * 1000),
            "datetime": row['datetime'].strftime("%Y-%m-%d %H:%M:%S"),
            "open": float(row['open']),
            "high": float(row['high']),
            "low": float(row['low']),
            "close": float(row['close']),
            "value": float(row['close']),
            "volume": int(row['volume'])
        })
    
    return jsonify(formatted_data)

@app.route('/collector/dates/<ticker>', methods=['GET'])
def get_collector_dates(ticker):
    """특정 종목의 데이터가 존재하는 날짜 목록 반환"""
    # 티커 정규화
    ticker = engine_instance.db.normalize_ticker(ticker)
    interval = request.args.get('interval', '5분')
    
    db_interval = engine_instance.db.map_interval(interval)
    
    try:
        # DB의 요약 정보 가져오기
        summaries = engine_instance.db.get_ohlcv_summaries(ticker, interval)
        if summaries:
            # 요약 정보가 있으면 그대로 반환
            return jsonify(summaries)
        
        # 요약 정보가 없는 경우 (예: 일봉 또는 아직 집계 안됨)
        # 기존 방식대로 날짜 목록만 가져옴
        dates = engine_instance.db.get_collected_dates(ticker, interval, "2000-01-01", "2099-12-31")
        return jsonify(dates)
    except Exception as e:
        logging.error(f"Error fetching collector dates: {e}")
        return jsonify([])

@app.route('/collector/tickers', methods=['GET'])
def get_collector_tickers():
    """수집된 데이터가 있는 티커 목록 반환 (이름 포함)"""
    try:
        conn = engine_instance.db.get_connection()
        try:
            with conn.cursor() as cur:
                # 1. tickers 테이블에서 모든 등록된 종목 가져오기
                cur.execute("SELECT ticker, name, buy_rule FROM tickers ORDER BY name ASC")
                db_tickers = cur.fetchall()
                
                # 2. ohlcv_* 테이블들에 존재하는 티커들 식별
                ohlcv_tickers = set()
                for table in ['ohlcv_1m', 'ohlcv_5m', 'ohlcv_1d']:
                    try:
                        cur.execute(f"SELECT DISTINCT ticker FROM {table}")
                        rows = cur.fetchall()
                        ohlcv_tickers.update({row['ticker'] for row in rows})
                    except Exception as e:
                        logging.warning(f"Failed to fetch tickers from {table}: {e}")
                
                # 3. KRX 캐시 및 주요 종목 매핑 활용 (이름 정규화)
                try:
                    name_map = engine_instance.collector.get_ticker_name_map()
                except Exception as e:
                    logging.error(f"Failed to get ticker name map: {e}")
                    name_map = {}
                
                # 주요 종목 하드코딩 (네트워크 장애 대비용)
                hardcoded_names = {
                    "005930": "삼성전자",
                    "122630": "KODEX 레버리지",
                    "252670": "KODEX 200선물인버스2X",
                    "114800": "KODEX 인버스",
                    "069500": "KODEX 200",
                    "000660": "SK하이닉스",
                    "005935": "삼성전자우",
                    "QQQ": "Invesco QQQ Trust",
                    "SQQQ": "ProShares UltraPro Short QQQ",
                    "TQQQ": "ProShares UltraPro QQQ",
                    "PSQ": "ProShares Short QQQ",
                    "AAPL": "Apple Inc.",
                    "MSFT": "Microsoft Corp",
                    "TSLA": "Tesla Inc",
                    "NVDA": "NVIDIA Corp"
                }
                
                results = []
                # tickers 테이블의 모든 종목 추가
                registered_normalized = {} 
                
                for row in db_tickers:
                    raw_ticker = row['ticker']
                    norm_ticker = engine_instance.db.normalize_ticker(raw_ticker)
                    
                    # 이름 찾기 우선순위: DB -> 하드코딩 -> KRX캐시 -> 티커
                    name = row['name']
                    if not name or name == raw_ticker:
                        name = hardcoded_names.get(norm_ticker) or name_map.get(raw_ticker) or name_map.get(norm_ticker) or raw_ticker
                    
                    item = {"ticker": raw_ticker, "name": name, "buy_rule": row.get('buy_rule', 'DEFAULT')}
                    results.append(item)
                    registered_normalized[norm_ticker] = item
                
                # ohlcv_data에는 있지만 tickers엔 없는 종목 추가
                for raw_ticker in ohlcv_tickers:
                    norm_ticker = engine_instance.db.normalize_ticker(raw_ticker)
                    
                    if norm_ticker not in registered_normalized:
                        name = hardcoded_names.get(norm_ticker) or name_map.get(raw_ticker) or name_map.get(norm_ticker) or raw_ticker
                        item = {"ticker": raw_ticker, "name": name, "buy_rule": "DEFAULT"}
                        results.append(item)
                        registered_normalized[norm_ticker] = item
                
                # 가나다순 정렬 (종목명 기준)
                results.sort(key=lambda x: (x['name'] == x['ticker'], x['name']))

                # [FIX] 이름 및 티커 중복 최종 제거 (정규화된 티커 기준)
                final_results = []
                seen_norm = set()
                for item in results:
                    norm = engine_instance.db.normalize_ticker(item['ticker'])
                    if norm not in seen_norm:
                        # 이름이 숫자로만 되어있는 경우 (검색 실패 시) 다시 한번 캐시 확인
                        if item['name'] == item['ticker'] or item['name'] == norm:
                            item['name'] = name_map.get(item['ticker']) or name_map.get(norm) or item['name']
                            
                        final_results.append(item)
                        seen_norm.add(norm)
                
                return jsonify(final_results)
        finally:
            conn.close()
    except Exception as e:
        logging.error(f"Error fetching collector tickers: {e}")
        return jsonify([])

@app.route('/simulation/reconstruct', methods=['POST'])
def reconstruct_simulation():
    data = request.json
    ticker = data.get('ticker')
    interval = data.get('interval', '1분')
    date = data.get('selectedDate')
    mode = data.get('mode', 'REALISTIC')
    density = int(data.get('density', 1))
    
    # 티커 정규화
    ticker = engine_instance.db.normalize_ticker(ticker)

    logging.info(f"Reconstruction request: {ticker} on {date} (source: {interval}, mode: {mode})")
    
    # 1. Fetch OHLCV data from DB
    db_interval = engine_instance.db.map_interval(interval)
    
    try:
        conn = engine_instance.db.get_connection()
        try:
            with conn.cursor() as cur:
                # 주기별 테이블 이름 가져오기
                table_name = engine_instance.db._get_ohlcv_table(db_interval)
                sql = f"""
                    SELECT datetime as ts, open, high, low, close, volume 
                    FROM {table_name}
                    WHERE ticker = %s AND DATE(datetime) = %s
                    ORDER BY ts ASC
                """
                cur.execute(sql, (ticker, date))
                rows = cur.fetchall()
        finally:
            conn.close()
            
        if not rows:
            return jsonify({"status": "ERROR", "message": "해당 날짜에 데이터가 없습니다."})
            
        import pandas as pd
        df_ohlcv = pd.DataFrame(rows)
        
        # Ensure numeric columns are float (fixes Decimal type errors)
        num_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in num_cols:
            if col in df_ohlcv.columns:
                df_ohlcv[col] = df_ohlcv[col].apply(float)
        
        # 2. Reconstruct Ticks
        from backend.simulator.generator import ReconstructionGenerator
        gen = ReconstructionGenerator(mode=mode, density=density, interval=interval)
        df_ticks = gen.generate_from_ohlcv(df_ohlcv)
        
        # 3. Handle generated ticks (Simulate real-time broadast)
        # For simplicity, we just send'SUCCESS' here. 
        # In a real scenario, we might save to parquet or start a replay.
        # But per user request "틱 데이터를 생성하려고 합니다", we'll just confirm creation.
        
        # Save to DB or CSV? For now let's just broadcast first tick as a proof of concept
        # or just return success and let the user view in chart
        
        # Store in tick_history for '차트 + 테이블' view
        if ticker not in tick_history: tick_history[ticker] = []
        
        new_ticks = []
        for _, row in df_ticks.iterrows():
            new_ticks.append({
                "time": int(row['ts'].timestamp() * 1000),
                "value": row['price'],
                "volume": row['volume'],
                "scenario": f"RECON:{mode}:{interval}",
                "marker": None
            })
        
        tick_history[ticker] = new_ticks # Replace or append? Let's replace for a fresh gen
        
        # 4. Save to MySQL for persistence
        saved_count = engine_instance.db.save_tick_data(ticker, df_ticks)
        logging.info(f"Persistent storage: {saved_count} ticks saved to DB for {ticker}")
        
        # 5. [FIX] Generate 1d Summary for Date Listing
        try:
            df_summary = df_ticks.copy()
            df_summary['date'] = pd.to_datetime(df_summary['ts']).dt.date
            # Calculate 1d OHLCV from ticks
            summary_1d = df_summary.groupby('date').agg({
                'price': ['first', 'max', 'min', 'last'],
                'volume': 'sum'
            })
            summary_1d.columns = ['open', 'high', 'low', 'close', 'volume']
            summary_1d.index = pd.to_datetime(summary_1d.index)
            # Save as '1d' interval
            engine_instance.db.save_ohlcv_data(ticker, '1d', summary_1d)
            logging.info(f"Generated 1d summary for {ticker} on {date}")
        except Exception as e:
            logging.error(f"Failed to generate 1d summary: {e}")
        
        return jsonify({
            "status": "SUCCESS", 
            "count": len(new_ticks),
            "ticker": ticker
        })
        
    except Exception as e:
        logging.error(f"Reconstruction failed: {e}")
        return jsonify({"status": "ERROR", "message": str(e)})

@app.route('/strategies/params', methods=['GET'])
def get_strategy_params():
    """전략 파일에서 파라미터 추출"""
    name = request.args.get('name')
    if not name:
        return jsonify({"status": "ERROR", "message": "전략 이름이 필요합니다."}), 400
    
    strat = engine_instance.strategy_mgr.get_strategy(name)
    if not strat:
        return jsonify({"status": "ERROR", "message": "전략을 찾을 수 없습니다."}), 404
    
    content = strat['content']
    import configparser
    import re
    
    config = configparser.ConfigParser(interpolation=None)
    try:
        config.read_string(content)
        
        # 섹션 찾기 ([설정] 또는 [INFO] 또는 첫 번째 섹션)
        section = None
        if '설정' in config: section = '설정'
        elif 'INFO' in config: section = 'INFO'
        elif config.sections(): section = config.sections()[0]
        
        if not section:
            return jsonify({"status": "ERROR", "message": "유효한 섹션을 찾을 수 없습니다."}), 400
            
        params = {}
        # 임계값 추출
        if '임계값' in config[section]:
            params['threshold'] = float(config.get(section, '임계값'))
            
        # 매수금액 추출
        if '매수금액' in config[section]:
            val = config.get(section, '매수금액')
            num_str = re.sub(r'[^\d]', '', val)
            if num_str:
                params['start_cash'] = float(num_str)
        
        return jsonify({"status": "SUCCESS", "params": params})
        
    except Exception as e:
        logging.error(f"Error parsing strategy params for {name}: {e}")
        return jsonify({"status": "ERROR", "message": str(e)}), 500

@app.route('/backtest/spread', methods=['POST'])
def run_spread_backtest():
    """듀얼 ETF 스프레드 백테스트 실행"""
    data = request.json
    ticker1 = data.get('ticker1', '069500')
    ticker2 = data.get('ticker2', '114800')
    threshold = float(data.get('threshold', 1.5))
    date = data.get('date')
    strategy_name = data.get('strategy')
    start_cash = float(data.get('start_cash', 0))  # 프론트엔드에서 전달된 매수금액
    logging.info(f"[backtest/spread] 📩 Request received - strategy='{strategy_name}', ticker1={ticker1}, ticker2={ticker2}, threshold={threshold}, start_cash={start_cash}, date={date}")
    
    if not date:
        return jsonify({"status": "ERROR", "message": "날짜를 선택해 주세요."}), 400
        
    from core.strategy.dual.spread_trader import IntradaySpreadTrader
    
    try:
        # 종목명 찾기
        name1 = engine_instance.resolve_ticker_name(ticker1)
        name2 = engine_instance.resolve_ticker_name(ticker2)
        
        trader = IntradaySpreadTrader(
            ticker1=ticker1, 
            ticker2=ticker2, 
            threshold=threshold,
            strategy_mgr=engine_instance.strategy_mgr,
            strategy_name=strategy_name,
            name1=name1,
            name2=name2
        )
        
        # 프론트엔드 설정값 강제 적용 (전략 파일 설정보다 우선)
        if start_cash > 0:
            trader.start_cash = start_cash
            trader.cash = start_cash
            logging.info(f"[backtest/spread] UI Override - start_cash: {start_cash:,.0f}")
            
        if threshold:
            trader.threshold = threshold
            logging.info(f"[backtest/spread] UI Override - threshold: {threshold:.2f}")
        
        result = trader.backtest(engine_instance.db, date)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Spread backtest failed: {e}")
        return jsonify({"status": "ERROR", "message": str(e)}), 500

@app.route('/collector/import', methods=['POST'])
def import_collector_data():
    if 'file' not in request.files:
        return jsonify({"status": "ERROR", "message": "파일이 없습니다."}), 400
    
    file = request.files['file']
    ticker = request.form.get('ticker')
    interval = request.form.get('interval')
    
    if not ticker or not interval:
        return jsonify({"status": "ERROR", "message": "종목 또는 주기가 선택되지 않았습니다."}), 400
    
    try:
        import pandas as pd
        import io
        
        # Read CSV
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        df = pd.read_csv(stream)
        
        # Validation & Type Conversion
        if 'datetime' not in df.columns:
            return jsonify({"status": "ERROR", "message": "CSV에 'datetime' 컬럼이 필요합니다."}), 400
            
        df['datetime'] = pd.to_datetime(df['datetime'])
        
        if interval == '틱':
            # Tick data validation
            required = ['price', 'volume']
            if not all(col in df.columns for col in required):
                return jsonify({"status": "ERROR", "message": "틱 데이터에는 price, volume 컬럼이 필요합니다."}), 400
            
            # Scenario handling (Prefer explicit columns, fallback to form)
            if 'algorithm' in df.columns and 'base' in df.columns:
                # Use columns from CSV if they exist (new export format)
                df['scenario'] = "RECON:" + df['algorithm'].astype(str) + ":" + df['base'].astype(str)
            elif 'scenario' in df.columns:
                # Use existing scenario column (legacy export format)
                pass 
            else:
                # Fallback to form values
                algo = request.form.get('algorithm', 'UNKNOWN')
                base = request.form.get('baseInterval', 'UNKNOWN')
                df['scenario'] = f"RECON:{algo}:{base}"
            
            # Rename columns to match DB if needed (df_ticks expects 'ts', 'price', 'volume', 'scenario')
            # But DB save_tick_data expects a DF with these cols. 
            # In ReconstructionGenerator it uses 'ts'. Let's align.
            df = df.rename(columns={'datetime': 'ts'})
            
            count = engine_instance.db.save_tick_data(ticker, df)
            
            # [FIX] Generate 1d Summary for Date Listing from Imported Ticks
            try:
                df_summary = df.copy()
                df_summary['date'] = pd.to_datetime(df_summary['ts']).dt.date
                summary_1d = df_summary.groupby('date').agg({
                    'price': ['first', 'max', 'min', 'last'],
                    'volume': 'sum'
                })
                summary_1d.columns = ['open', 'high', 'low', 'close', 'volume']
                summary_1d.index = pd.to_datetime(summary_1d.index)
                engine_instance.db.save_ohlcv_data(ticker, '1d', summary_1d)
                logging.info(f"Generated 1d summary for {ticker} from imported ticks")
            except Exception as e:
                logging.error(f"Failed to generate 1d summary from import: {e}")
        else:
            # OHLCV data validation
            required = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required):
                return jsonify({"status": "ERROR", "message": "OHLCV 데이터에는 open, high, low, close, volume 컬럼이 필요합니다."}), 400
            
            # Map interval to DB format
            db_interval = engine_instance.db.map_interval(interval)
            
            # Save OHLCV
            # We need a method in DB to save bulk OHLCV. 
            # Currently DB has save_ohlcv_data(ticker, interval, df)
            count = engine_instance.db.save_ohlcv_data(ticker, db_interval, df)
            
        return jsonify({
            "status": "SUCCESS",
            "message": f"{count}건의 데이터가 성공적으로 저장되었습니다.",
            "count": count
        })
        
    except Exception as e:
        logging.error(f"Import failed: {str(e)}")
        return jsonify({"status": "ERROR", "message": str(e)}), 500

@app.route('/collector/delete/<ticker>', methods=['DELETE'])
def delete_collector_data(ticker):
    date = request.args.get('date')
    ui_interval = request.args.get('interval')
    
    # UI 인터벌 -> DB 인터벌 변환
    db_interval = engine_instance.db.map_interval(ui_interval)
    
    try:
        if date:
            if db_interval:
                # 1. 특정 간격의 데이터만 삭제
                if db_interval == 'tick':
                    engine_instance.db.delete_tick_data(ticker, date_str=date)
                    if ticker in tick_history:
                        del tick_history[ticker]
                else:
                    engine_instance.db.delete_ohlcv_data(ticker, db_interval, start_date=date, end_date=date)
                
                logging.info(f"Ticker date interval data deleted: {ticker} ({date}, {db_interval})")
                return jsonify({"status": "SUCCESS", "message": f"'{ticker}'의 {date} ({ui_interval}) 데이터가 삭제되었습니다."})
            else:
                # 2. 특정 날짜의 모든 간격 데이터 삭제 (기존 동작)
                engine_instance.db.delete_tick_data(ticker, date_str=date)
                for interval in ['1m', '5m', '1d']:
                    engine_instance.db.delete_ohlcv_data(ticker, interval, start_date=date, end_date=date)
                
                if ticker in tick_history:
                    del tick_history[ticker]
                    
                logging.info(f"Ticker date data deleted: {ticker} ({date})")
                return jsonify({"status": "SUCCESS", "message": f"'{ticker}'의 {date} 모든 데이터가 삭제되었습니다."})
        else:
            # 3. 해당 티커의 모든 정보 삭제
            success = engine_instance.db.delete_ticker_data(ticker)
            if success:
                if ticker in tick_history:
                    del tick_history[ticker]
                logging.info(f"All ticker data deleted: {ticker}")
                return jsonify({"status": "SUCCESS", "message": f"'{ticker}'의 모든 데이터가 삭제되었습니다."})
            else:
                return jsonify({"status": "ERROR", "message": "데이터 삭제 중 오류가 발생했습니다."}), 500
            
    except Exception as e:
        logging.error(f"Delete failed: {str(e)}")
        return jsonify({"status": "ERROR", "message": str(e)}), 500

# --- Claude CLI / Antigravity CLI 연동 API ---
# 훅 스크립트(cli_hook_prompt.py / cli_hook_stop.py)가 CLI 프롬프트와 응답을 기록한다.
try:
    from backend import cli_tasks
except ImportError:
    import cli_tasks

cli_tasks.init_db()

@app.route('/cli/tasks', methods=['GET'])
def cli_tasks_list():
    try:
        tasks = cli_tasks.list_tasks(
            limit=request.args.get('limit', 50),
            trigger_type=request.args.get('trigger_type'),
        )
        return jsonify(tasks)
    except Exception as e:
        logging.error(f"CLI tasks list failed: {e}")
        return jsonify({"status": "ERROR", "message": str(e)}), 500

@app.route('/cli/tasks', methods=['POST'])
def cli_tasks_add():
    data = request.json or {}
    prompt = data.get('prompt') or ''
    title = (data.get('title') or '').strip() or (prompt.split('\n')[0].strip() or 'CLI 작업')[:100]
    try:
        task_id = cli_tasks.add_task(
            title=title,
            prompt=prompt,
            trigger_type=data.get('trigger_type', 'claude_cli'),
            session_id=data.get('session_id', ''),
            cwd=data.get('cwd', ''),
        )
        return jsonify({"status": "SUCCESS", "id": task_id})
    except Exception as e:
        logging.error(f"CLI task add failed: {e}")
        return jsonify({"status": "ERROR", "message": str(e)}), 500

@app.route('/cli/tasks/<int:task_id>', methods=['GET'])
def cli_tasks_get(task_id):
    task = cli_tasks.get_task(task_id)
    if not task:
        return jsonify({"status": "ERROR", "message": "not found"}), 404
    return jsonify(task)

@app.route('/cli/tasks/<int:task_id>', methods=['DELETE'])
def cli_tasks_delete(task_id):
    if cli_tasks.delete_task(task_id):
        return jsonify({"status": "SUCCESS"})
    return jsonify({"status": "ERROR", "message": "not found"}), 404

@app.route('/cli/tasks/delete-bulk', methods=['POST'])
def cli_tasks_delete_bulk():
    # 선택된 CLI 작업 일괄 삭제
    ids = (request.json or {}).get('ids') or []
    deleted = 0
    for tid in ids:
        try:
            if cli_tasks.delete_task(int(tid)):
                deleted += 1
        except (ValueError, TypeError):
            continue
    return jsonify({"status": "SUCCESS", "deleted": deleted})

@app.route('/cli/tasks/<int:task_id>/log-result', methods=['POST'])
def cli_tasks_log_result(task_id):
    data = request.json or {}
    try:
        ok = cli_tasks.log_result(
            task_id,
            answer=data.get('answer', ''),
            output=data.get('output', ''),
            status=data.get('status', 'done'),
            model=data.get('model', ''),
            cli_session_id=data.get('cli_session_id', ''),
            duration_ms=data.get('duration_ms', 0),
            log_lines=data.get('log_lines'),
            trigger_type=data.get('trigger_type'),
        )
        if not ok:
            return jsonify({"status": "ERROR", "message": "not found"}), 404
        return jsonify({"status": "SUCCESS"})
    except Exception as e:
        logging.error(f"CLI task log-result failed: {e}")
        return jsonify({"status": "ERROR", "message": str(e)}), 500

# --- AI 추천 종목 API (Claude CLI 기반) ---
try:
    from backend import ai_picks
except ImportError:
    import ai_picks

ai_picks.init_db()

@app.route('/ai-picks', methods=['GET'])
def ai_picks_list():
    try:
        return jsonify(ai_picks.list_profiles())
    except Exception as e:
        logging.error(f"AI picks list failed: {e}")
        return jsonify({"status": "ERROR", "message": str(e)}), 500

@app.route('/ai-picks/stocks', methods=['GET'])
def ai_picks_stocks():
    # AI 종목이 선별한 종목 목록 (AI 매매의 대상 종목 선택용)
    try:
        return jsonify(ai_picks.list_result_stocks())
    except Exception as e:
        logging.error(f"AI picks stocks failed: {e}")
        return jsonify({"status": "ERROR", "message": str(e)}), 500

@app.route('/ai-picks/models', methods=['GET'])
def ai_picks_models():
    # 선택 가능한 AI 모델 목록 (성능 순)
    return jsonify({"models": ai_picks.AVAILABLE_MODELS, "default": ai_picks.DEFAULT_MODEL})

@app.route('/ai-picks', methods=['POST'])
def ai_picks_add():
    data = request.json or {}
    try:
        pid = ai_picks.add_profile(data.get('name'), data.get('prompt'), model=data.get('model'), market=data.get('market'))
        return jsonify({"status": "SUCCESS", "id": pid})
    except ValueError as e:
        return jsonify({"status": "ERROR", "message": str(e)}), 400
    except Exception as e:
        msg = "이미 같은 이름의 프로파일이 있습니다." if "UNIQUE" in str(e) else str(e)
        return jsonify({"status": "ERROR", "message": msg}), 400

@app.route('/ai-picks/<int:pid>', methods=['PUT'])
def ai_picks_update(pid):
    data = request.json or {}
    try:
        if ai_picks.update_profile(pid, data.get('name'), data.get('prompt'), model=data.get('model'), market=data.get('market')):
            return jsonify({"status": "SUCCESS"})
        return jsonify({"status": "ERROR", "message": "not found"}), 404
    except ValueError as e:
        return jsonify({"status": "ERROR", "message": str(e)}), 400
    except Exception as e:
        msg = "이미 같은 이름의 프로파일이 있습니다." if "UNIQUE" in str(e) else str(e)
        return jsonify({"status": "ERROR", "message": msg}), 400

@app.route('/ai-picks/<int:pid>', methods=['DELETE'])
def ai_picks_delete(pid):
    if ai_picks.delete_profile(pid):
        return jsonify({"status": "SUCCESS"})
    return jsonify({"status": "ERROR", "message": "not found"}), 404

@app.route('/ai-picks/<int:pid>/run', methods=['POST'])
def ai_picks_run(pid):
    try:
        started = ai_picks.run_profile(pid)
        if started:
            return jsonify({"status": "SUCCESS", "message": "실행 시작"})
        return jsonify({"status": "RUNNING", "message": "이미 실행 중입니다."})
    except ValueError as e:
        return jsonify({"status": "ERROR", "message": str(e)}), 404
    except Exception as e:
        logging.error(f"AI picks run failed: {e}")
        return jsonify({"status": "ERROR", "message": str(e)}), 500

@app.route('/ai-picks/<int:pid>/result', methods=['GET'])
def ai_picks_result(pid):
    result = ai_picks.get_result(pid)
    if not result:
        return jsonify({"status": "NONE"})
    return jsonify(result)

@app.route('/ai-picks/<int:pid>/compare', methods=['POST'])
def ai_picks_compare(pid):
    # 선별 결과 종목들의 재무제표/투자지표 상세 비교 실행
    try:
        started = ai_picks.run_comparison(pid)
        if started:
            return jsonify({"status": "SUCCESS", "message": "비교 분석 시작"})
        return jsonify({"status": "RUNNING", "message": "이미 실행 중입니다."})
    except ValueError as e:
        return jsonify({"status": "ERROR", "message": str(e)}), 400
    except Exception as e:
        logging.error(f"AI picks compare failed: {e}")
        return jsonify({"status": "ERROR", "message": str(e)}), 500

@app.route('/ai-picks/<int:pid>/comparison', methods=['GET'])
def ai_picks_comparison(pid):
    result = ai_picks.get_comparison(pid)
    if not result:
        return jsonify({"status": "NONE"})
    return jsonify(result)

@app.route('/ai-picks/<int:pid>/comparison/export-gsheet', methods=['POST'])
def ai_picks_comparison_export(pid):
    # 상세 비교 결과를 구글 시트에 업로드 (탭 이름 = 프로파일명)
    comp = ai_picks.get_comparison(pid)
    if not comp or comp.get("status") != "done" or not comp.get("comparison"):
        return jsonify({"status": "ERROR",
                        "message": "업로드할 비교 결과가 없습니다. 먼저 상세 비교를 실행하세요."}), 400

    profile = next((p for p in ai_picks.list_profiles() if p["id"] == pid), None)
    if not profile:
        return jsonify({"status": "ERROR", "message": "프로파일이 없습니다."}), 404

    try:
        from core.service.gsheet_exporter import GSheetExporter, GSheetConfigError
        try:
            exporter = GSheetExporter()
            result = exporter.export_comparison(
                profile["name"], comp["comparison"], finished_at=comp.get("finished_at"))
            engine_instance.add_log(
                f"AI 종목 상세 비교 구글 시트 업로드 완료 ({result.get('sheet')}, {result['rows']}종목)")
            return jsonify({"status": "SUCCESS", **result})
        except GSheetConfigError as e:
            return jsonify({"status": "CONFIG_ERROR", "message": str(e)}), 400
    except Exception as e:
        logging.error(f"AI picks comparison export failed: {e}", exc_info=True)
        return jsonify({"status": "ERROR", "message": str(e)}), 500

# --- AI 매매 API (종목별 매매 전략 문의) ---
try:
    from backend import ai_trades
except ImportError:
    import ai_trades

ai_trades.init_db()

@app.route('/ai-trades', methods=['GET'])
def ai_trades_list():
    try:
        return jsonify(ai_trades.list_profiles())
    except Exception as e:
        logging.error(f"AI trades list failed: {e}")
        return jsonify({"status": "ERROR", "message": str(e)}), 500

@app.route('/ai-trades', methods=['POST'])
def ai_trades_add():
    data = request.json or {}
    try:
        tid = ai_trades.add_profile(data.get('name'), data.get('prompt'), model=data.get('model'), market=data.get('market'))
        return jsonify({"status": "SUCCESS", "id": tid})
    except ValueError as e:
        return jsonify({"status": "ERROR", "message": str(e)}), 400
    except Exception as e:
        msg = "이미 같은 이름의 프로파일이 있습니다." if "UNIQUE" in str(e) else str(e)
        return jsonify({"status": "ERROR", "message": msg}), 400

@app.route('/ai-trades/<int:tid>', methods=['PUT'])
def ai_trades_update(tid):
    data = request.json or {}
    try:
        if ai_trades.update_profile(tid, data.get('name'), data.get('prompt'), model=data.get('model'), market=data.get('market')):
            return jsonify({"status": "SUCCESS"})
        return jsonify({"status": "ERROR", "message": "not found"}), 404
    except ValueError as e:
        return jsonify({"status": "ERROR", "message": str(e)}), 400
    except Exception as e:
        msg = "이미 같은 이름의 프로파일이 있습니다." if "UNIQUE" in str(e) else str(e)
        return jsonify({"status": "ERROR", "message": msg}), 400

@app.route('/ai-trades/<int:tid>', methods=['DELETE'])
def ai_trades_delete(tid):
    if ai_trades.delete_profile(tid):
        return jsonify({"status": "SUCCESS"})
    return jsonify({"status": "ERROR", "message": "not found"}), 404

@app.route('/ai-trades/<int:tid>/run', methods=['POST'])
def ai_trades_run(tid):
    data = request.json or {}
    try:
        started = ai_trades.run_profile(tid, data.get('ticker'), data.get('ticker_name', ''))
        if started:
            return jsonify({"status": "SUCCESS", "message": "실행 시작"})
        return jsonify({"status": "RUNNING", "message": "이미 실행 중입니다."})
    except ValueError as e:
        return jsonify({"status": "ERROR", "message": str(e)}), 400
    except Exception as e:
        logging.error(f"AI trades run failed: {e}")
        return jsonify({"status": "ERROR", "message": str(e)}), 500

@app.route('/ai-trades/<int:tid>/result', methods=['GET'])
def ai_trades_result(tid):
    result = ai_trades.get_result(tid)
    if not result:
        return jsonify({"status": "NONE"})
    return jsonify(result)

@app.route('/ai-trades/<int:tid>/run-batch', methods=['POST'])
def ai_trades_run_batch(tid):
    # 여러 종목(보유 종목 전체 등)을 한 프로파일로 순차 분석
    data = request.json or {}
    items = data.get('items')
    if items is None and data.get('holdings') is True:
        account = engine_instance.data_store.get("account") or {}
        items = [{"ticker": h.get("ticker"), "name": h.get("name")}
                 for h in (account.get("holdings") or []) if isinstance(h, dict)]
    try:
        started = ai_trades.run_batch(tid, items)
        if started:
            engine_instance.add_log(
                f"AI 매매 일괄 분석 시작 (프로파일 {tid}, {len(items)}종목)")
            return jsonify({"status": "SUCCESS", "total": len(items)})
        return jsonify({"status": "RUNNING", "message": "이미 실행 중입니다."})
    except ValueError as e:
        return jsonify({"status": "ERROR", "message": str(e)}), 400
    except Exception as e:
        logging.error(f"AI trades batch failed: {e}", exc_info=True)
        return jsonify({"status": "ERROR", "message": str(e)}), 500

@app.route('/ai-trades/<int:tid>/batch-status', methods=['GET'])
def ai_trades_batch_status(tid):
    return jsonify(ai_trades.get_batch_status(tid))

@app.route('/ai-trades/strategies', methods=['GET'])
def ai_trades_strategies():
    # 완료된 매매 전략을 종목코드별로 반환 (보유 종목에서 해당 종목 전략 표시용)
    return jsonify(ai_trades.list_strategies())

@app.route('/ai-trades/<int:tid>/export-gsheet', methods=['POST'])
def ai_trades_export(tid):
    # 매매 전략을 구글 시트에 업로드 (탭 이름 = 프로파일명, 같은 종목이면 갱신)
    result = ai_trades.get_result(tid)
    if not result or result.get("status") != "done" or not result.get("strategy"):
        return jsonify({"status": "ERROR",
                        "message": "업로드할 매매 전략이 없습니다. 먼저 전략 분석을 실행하세요."}), 400

    profile = next((p for p in ai_trades.list_profiles() if p["id"] == tid), None)
    if not profile:
        return jsonify({"status": "ERROR", "message": "프로파일이 없습니다."}), 404

    try:
        from core.service.gsheet_exporter import GSheetExporter, GSheetConfigError
        try:
            exporter = GSheetExporter()
            res = exporter.export_strategy(
                profile["name"], result["strategy"], finished_at=result.get("finished_at"))
            action = "갱신" if res.get("updated") else "추가"
            engine_instance.add_log(
                f"AI 매매 전략 구글 시트 {action} ({res.get('sheet')}, {res.get('ticker_name')})")
            return jsonify({"status": "SUCCESS", **res})
        except GSheetConfigError as e:
            return jsonify({"status": "CONFIG_ERROR", "message": str(e)}), 400
    except Exception as e:
        logging.error(f"AI trades export failed: {e}", exc_info=True)
        return jsonify({"status": "ERROR", "message": str(e)}), 500

# --- AI Notice API (메신저로 나간 AI 알림 조회) ---
try:
    from backend import ai_notices
except ImportError:
    import ai_notices

ai_notices.init_db()

@app.route('/ai-notices', methods=['GET'])
def ai_notices_list():
    # 최신순 알림 목록. after_id로 신규분만 폴링 가능
    return jsonify({"notices": ai_notices.list_notices(
        limit=request.args.get('limit', 100),
        category=request.args.get('category'),
        after_id=request.args.get('after_id'),
        market=request.args.get('market'))})

@app.route('/ai-notices/clear', methods=['POST'])
def ai_notices_clear():
    deleted = ai_notices.clear_all()
    return jsonify({"status": "SUCCESS", "deleted": deleted})

# --- 전략 이탈 감시 API (보유 종목 현재가 vs AI 전략 손절가/목표가) ---
try:
    from backend import strategy_monitor
except ImportError:
    import strategy_monitor

@app.route('/strategy-monitor', methods=['GET'])
def strategy_monitor_status():
    # 감시 설정/실행 상태와 최근 알림 이력
    return jsonify(strategy_monitor.get_status())

@app.route('/strategy-monitor/config', methods=['POST'])
def strategy_monitor_config():
    # 감시 설정 변경 (enabled, interval_sec, near_stop_pct, auto_reanalyze, market_open/close)
    try:
        cfg = strategy_monitor.update_config(request.json or {})
        return jsonify({"status": "SUCCESS", "config": cfg})
    except (TypeError, ValueError) as e:
        return jsonify({"status": "ERROR", "message": f"잘못된 설정 값: {e}"}), 400

@app.route('/strategy-monitor/check-now', methods=['POST'])
def strategy_monitor_check_now():
    # 즉시 1회 점검. dry_run=true면 알림 없이 평가 결과만 반환 (테스트용)
    req = request.json or {}
    result = strategy_monitor.check_once(
        refresh=bool(req.get("refresh", True)),
        dry_run=bool(req.get("dry_run", False)),
        force=bool(req.get("force", True)))
    if "error" in result:
        return jsonify({"status": "ERROR", "message": result["error"]}), 500
    return jsonify({"status": "SUCCESS", **result})

# --- AI 전략 스코어카드 API (전략 목표/손절 도달 자동 채점) ---
try:
    from backend import strategy_scorecard
except ImportError:
    import strategy_scorecard

strategy_scorecard.init_db()

@app.route('/strategy-scorecard', methods=['GET'])
def scorecard_list():
    # 채점 결과 상세 + 프로파일/모델별 집계
    return jsonify({"stats": strategy_scorecard.get_stats(),
                    "rows": strategy_scorecard.list_rows()})

@app.route('/strategy-scorecard/grade', methods=['POST'])
def scorecard_grade():
    # 전략 스냅샷 저장 + 미확정 전략 채점 (일봉 조회 → 수십 초 걸릴 수 있음)
    result = strategy_scorecard.grade()
    if "error" in result:
        return jsonify({"status": "ERROR", "message": result["error"]}), 409
    return jsonify({"status": "SUCCESS", **result})

@app.route('/strategy-scorecard/export-gsheet', methods=['POST'])
def scorecard_export():
    # 채점 결과를 구글 시트 '전략성과'/'전략성과요약' 탭에 업로드
    try:
        from core.service.gsheet_exporter import GSheetExporter, GSheetConfigError
        try:
            exporter = GSheetExporter()
            res = exporter.export_scorecard(
                strategy_scorecard.list_rows(),
                strategy_scorecard.get_stats(),
                graded_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            engine_instance.add_log(f"전략 성과 구글 시트 업로드 완료 ({res['rows']}건)")
            return jsonify({"status": "SUCCESS", **res})
        except GSheetConfigError as e:
            return jsonify({"status": "CONFIG_ERROR", "message": str(e)}), 400
    except Exception as e:
        logging.error(f"Scorecard export failed: {e}", exc_info=True)
        return jsonify({"status": "ERROR", "message": str(e)}), 500

# --- 매매일지 AI 복기 API (주간 리포트) ---
try:
    from backend import ai_review
except ImportError:
    import ai_review

@app.route('/ai-review', methods=['GET'])
def ai_review_list():
    return jsonify({"config": ai_review.get_config(),
                    "reviews": ai_review.list_reviews()})

@app.route('/ai-review/latest', methods=['GET'])
def ai_review_latest():
    return jsonify(ai_review.get_review() or {})

@app.route('/ai-review/run', methods=['POST'])
def ai_review_run():
    # 복기 실행 (기본: 어제까지 최근 7일). 완료 시 디스코드/구글시트 자동 전달
    req = request.json or {}
    try:
        started = ai_review.run(engine_instance.db,
                                start=req.get('start'), end=req.get('end'),
                                model=req.get('model'))
        if started:
            engine_instance.add_log("매매일지 AI 복기 시작")
            return jsonify({"status": "SUCCESS"})
        return jsonify({"status": "RUNNING", "message": "이미 복기가 실행 중입니다."})
    except Exception as e:
        logging.error(f"AI review run failed: {e}", exc_info=True)
        return jsonify({"status": "ERROR", "message": str(e)}), 500

@app.route('/ai-review/config', methods=['POST'])
def ai_review_config():
    try:
        return jsonify({"status": "SUCCESS", "config": ai_review.update_config(request.json or {})})
    except (TypeError, ValueError) as e:
        return jsonify({"status": "ERROR", "message": f"잘못된 설정 값: {e}"}), 400

# --- 보유종목 아침 브리핑 API ---
try:
    from backend import ai_briefing
except ImportError:
    import ai_briefing

@app.route('/ai-briefing', methods=['GET'])
def ai_briefing_list():
    return jsonify({"config": ai_briefing.get_config(),
                    "briefings": ai_briefing.list_briefings()})

@app.route('/ai-briefing/latest', methods=['GET'])
def ai_briefing_latest():
    date = request.args.get('date')
    return jsonify(ai_briefing.get_briefing(date) or {})

@app.route('/ai-briefing/run', methods=['POST'])
def ai_briefing_run():
    # 브리핑 실행 (웹 검색 포함 → 수 분 소요). 완료 시 디스코드 자동 전달
    req = request.json or {}
    try:
        started = ai_briefing.run(date=req.get('date'), model=req.get('model'))
        if started:
            engine_instance.add_log("아침 브리핑 생성 시작")
            return jsonify({"status": "SUCCESS"})
        return jsonify({"status": "RUNNING", "message": "이미 브리핑이 실행 중입니다."})
    except Exception as e:
        logging.error(f"AI briefing run failed: {e}", exc_info=True)
        return jsonify({"status": "ERROR", "message": str(e)}), 500

@app.route('/ai-briefing/config', methods=['POST'])
def ai_briefing_config():
    try:
        return jsonify({"status": "SUCCESS", "config": ai_briefing.update_config(request.json or {})})
    except (TypeError, ValueError) as e:
        return jsonify({"status": "ERROR", "message": f"잘못된 설정 값: {e}"}), 400

# --- AI 캘린더 API (날짜별 주요 일정 + 일정 기반 매매 타이밍) ---
try:
    from backend import ai_calendar
except ImportError:
    import ai_calendar

ai_calendar.init_db()

@app.route('/ai-calendar', methods=['GET'])
def ai_calendar_list():
    return jsonify(ai_calendar.list_profiles())

@app.route('/ai-calendar', methods=['POST'])
def ai_calendar_add():
    data = request.json or {}
    try:
        pid = ai_calendar.add_profile(data.get('name'), data.get('prompt'), data.get('model'), market=data.get('market'))
        return jsonify({"status": "SUCCESS", "id": pid})
    except ValueError as e:
        return jsonify({"status": "ERROR", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e)}), 500

@app.route('/ai-calendar/<int:cid>', methods=['PUT'])
def ai_calendar_update(cid):
    data = request.json or {}
    try:
        ok = ai_calendar.update_profile(cid, data.get('name'), data.get('prompt'), data.get('model'), market=data.get('market'))
        return jsonify({"status": "SUCCESS" if ok else "ERROR"})
    except ValueError as e:
        return jsonify({"status": "ERROR", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e)}), 500

@app.route('/ai-calendar/<int:cid>', methods=['DELETE'])
def ai_calendar_delete(cid):
    ok = ai_calendar.delete_profile(cid)
    return jsonify({"status": "SUCCESS" if ok else "ERROR"})

@app.route('/ai-calendar/<int:cid>/run', methods=['POST'])
def ai_calendar_run(cid):
    try:
        started = ai_calendar.run_profile(cid)
        if started:
            return jsonify({"status": "SUCCESS", "message": "실행 시작"})
        return jsonify({"status": "RUNNING", "message": "이미 실행 중입니다."})
    except ValueError as e:
        return jsonify({"status": "ERROR", "message": str(e)}), 400
    except Exception as e:
        logging.error(f"AI calendar run failed: {e}")
        return jsonify({"status": "ERROR", "message": str(e)}), 500

@app.route('/ai-calendar/<int:cid>/result', methods=['GET'])
def ai_calendar_result(cid):
    result = ai_calendar.get_result(cid)
    if not result:
        return jsonify({"status": "NONE"})
    return jsonify(result)

# --- 도우미 채팅 API (Claude CLI 기반) ---
try:
    from backend import helper_chat
except ImportError:
    import helper_chat

helper_chat.init_db()

@app.route('/cli/chat/history', methods=['GET'])
def cli_chat_history():
    try:
        return jsonify(helper_chat.get_history(limit=request.args.get('limit', 50)))
    except Exception as e:
        logging.error(f"Chat history failed: {e}")
        return jsonify([]), 500

@app.route('/cli/chat/message', methods=['POST'])
def cli_chat_message():
    data = request.json or {}
    if helper_chat.add_message(data.get('role', ''), data.get('text', '')):
        return jsonify({"status": "SUCCESS"})
    return jsonify({"status": "ERROR", "message": "invalid message"}), 400

@app.route('/cli/chat/clear', methods=['POST'])
def cli_chat_clear():
    helper_chat.clear_history()
    return jsonify({"status": "SUCCESS"})

@app.route('/cli/chat/stream', methods=['POST'])
def cli_chat_stream():
    data = request.json or {}
    return Response(
        stream_with_context(helper_chat.stream_chat(data.get('message'), data.get('history'))),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )

def auto_reconnect_last_session():
    """
    서비스 시작 시 마지막으로 성공한 연결 정보(last_connection)로 자동 재연결.
    - VIRTUAL/KIS/바이낸스: /login 호출 즉시 결과 확인
    - 키움(32bit 게이트웨이): 게이트웨이 기동(UAC 승인 포함)에 시간이 걸리므로
      응답(LOGIN_RESULT)이 없으면 일정 간격으로 LOGIN을 재전송함
    """
    last = getattr(engine_instance, "last_connection", None)
    if not last or not last.get("mode"):
        # 과거 버전에서 저장된 설정(current_mode + 해당 계정 정보)으로 폴백
        cur_mode = engine_instance.current_mode
        acc = engine_instance.accounts.get(cur_mode) if cur_mode in ("REAL", "MOCK", "VIRTUAL") else None
        if acc and acc.get("acc_no"):
            last = {
                "mode": cur_mode,
                "asset_type": acc.get("asset_type", "STOCK"),
                "broker": acc.get("broker", "KIWOOM")
            }
            logging.info(f"[자동 재연결] last_connection 없음 → 기존 설정으로 폴백: {last}")
        else:
            logging.info("[자동 재연결] 저장된 연결 정보 없음 — 수동 연결 대기")
            return

    if os.getenv("JBRAIN_AUTO_RECONNECT", "1") != "1":
        logging.info("[자동 재연결] JBRAIN_AUTO_RECONNECT=0 → 자동 재연결 비활성화")
        return

    mode = last.get("mode")
    asset_type = last.get("asset_type", "STOCK")
    broker = last.get("broker", "KIWOOM")

    # 게이트웨이/서비스 기동 대기
    time.sleep(10)

    engine_instance.add_log(f"[자동 재연결] 마지막 연결 정보로 재연결 시도 (모드: {mode}, 자산: {asset_type}, 브로커: {broker})")

    # 주식 연결이면 해당 모드 계정의 브로커를 마지막 연결 브로커로 복원
    if asset_type == "STOCK" and mode in ("REAL", "MOCK") and broker in ("KIWOOM", "KOREA_INVESTMENT"):
        engine_instance.accounts[mode]["broker"] = broker

    client = app.test_client()
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        if str(engine_instance.status).startswith("CONNECTED"):
            return
        try:
            resp = client.post('/login', json={"mode": mode, "asset_type": asset_type})
            result = resp.get_json() or {}
        except Exception as e:
            logging.error(f"[자동 재연결] 로그인 요청 실패: {e}")
            time.sleep(10)
            continue

        status = result.get("status")
        if status == "CONNECTED":
            engine_instance.add_log("[자동 재연결] 재연결 성공")
            return
        if status in ("ERROR", "TIME_ERROR"):
            engine_instance.add_log(f"[자동 재연결] 중단: {result.get('message', status)}")
            return

        # TRYING (키움 게이트웨이 경유): LOGIN_RESULT 응답 대기
        # 게이트웨이 자동로그인은 최대 65초 소요될 수 있으므로 충분히 기다린 뒤 재시도
        waited = 0
        while waited < 75:
            time.sleep(3)
            waited += 3
            st = str(engine_instance.status)
            if st.startswith("CONNECTED"):
                engine_instance.add_log("[자동 재연결] 재연결 성공")
                return
            if st.startswith("ERROR"):
                engine_instance.add_log(f"[자동 재연결] 로그인 실패로 중단: {st}")
                return

        engine_instance.add_log(f"[자동 재연결] 게이트웨이 응답 없음 — 재시도 ({attempt}/{max_attempts})")

    engine_instance.add_log("[자동 재연결] 최종 실패 — '연결 설정'에서 수동으로 연결해 주세요.")

def kill_port_owner(port):
    """지정한 포트를 점유 중인 프로세스를 강제 종료함 (Windows 전용)"""
    try:
        import subprocess
        output = subprocess.check_output(f"netstat -ano | findstr :{port}", shell=True).decode('cp949', errors='ignore')
        for line in output.splitlines():
            if "LISTENING" in line:
                pid = line.strip().split()[-1]
                if pid.isdigit() and int(pid) != os.getpid():
                    logging.warning(f"Port {port} is occupied by PID {pid}. Terminating...")
                    subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
                    time.sleep(1) # 포트 해제 시간 확보
    except Exception as e:
        logging.debug(f"Port clear failed: {e}")

if __name__ == "__main__":
    # Werkzeug 디버거는 원격 코드 실행 벡터라 기본 비활성. 필요 시 JBRAIN_DEBUG=1로 활성화
    is_debug = os.getenv("JBRAIN_DEBUG", "0") == "1"
    
    # Reload 상태(자식 프로세스) 또는 디버그가 꺼진 경우에만 한 번 실행
    is_main_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not is_debug
    
    if is_main_process:
        # 8765 포트 충돌 방지를 위해 기존 프로세스 정리 시도
        kill_port_owner(8765)
        
        engine_instance = StrategyEngine()
        threading.Thread(target=start_ws_server, daemon=True).start()
        logging.info("<<< Backend Services (Engine + WebSocket) successfully started >>>")

        # 전략 이탈 감시 시작 (보유 종목 손절가/목표가 모니터링)
        strategy_monitor.start(engine_instance)

        # 마지막 연결 정보로 자동 재연결 (백그라운드)
        threading.Thread(target=auto_reconnect_last_session, daemon=True).start()

        # AI 전략 스코어카드 (평일 장 마감 후 자동 채점)
        strategy_scorecard.start()

        # 매매일지 AI 복기 (주 1회 자동) / 아침 브리핑 (평일 아침 자동)
        ai_review.start(engine_instance)
        ai_briefing.start(engine_instance)

        # Discord Bot 통합 실행 (같은 프로세스, 별도 스레드)
        if DISCORD_BOT_AVAILABLE:
            try:
                start_discord_bot(engine_instance)
                logging.info("<<< Discord Bot thread started >>>")
            except Exception as e:
                logging.warning(f"Discord Bot 시작 실패 (봇 없이 계속 실행): {e}")
    else:
        # 부모 프로세스는 모니터링 역할만 수행
        engine_instance = None
        logging.info("Flask reloader parent process active...")

    # 모바일 앱 등 LAN 접속이 필요 없으면 BACKEND_HOST=127.0.0.1 로 제한 권장
    app.run(host=os.getenv('BACKEND_HOST', '0.0.0.0'), port=5000, debug=is_debug)

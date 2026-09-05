import requests
import json
import logging
import os
import time
import hmac
import hashlib
from urllib.parse import urlencode
from datetime import datetime


class BinanceBroker:
    """
    Binance REST API Broker
    암호화폐 거래를 위한 바이낸스 API 연동 클래스
    현물(Spot) 및 선물(Futures) 모두 지원
    """
    def __init__(self, api_key=None, api_secret=None, is_testnet=False, market_type="FUTURES"):
        """
        Args:
            api_key: 바이낸스 API Key
            api_secret: 바이낸스 API Secret
            is_testnet: 테스트넷 사용 여부
            market_type: "SPOT" 또는 "FUTURES" (기본: FUTURES)
        """
        self.api_key = api_key or os.getenv("BINANCE_API_KEY")
        self.api_secret = api_secret or os.getenv("BINANCE_API_SECRET")
        self.is_testnet = is_testnet
        self.market_type = market_type.upper()

        # 시장 유형 + 테스트넷 여부에 따라 URL/경로 결정
        if self.market_type == "FUTURES":
            if self.is_testnet:
                self.base_url = "https://testnet.binancefuture.com"
            else:
                self.base_url = "https://fapi.binance.com"
            self.api_prefix = "/fapi"
        else:  # SPOT
            if self.is_testnet:
                self.base_url = "https://testnet.binance.vision"
            else:
                self.base_url = "https://api.binance.com"
            self.api_prefix = "/api"

        self.connected = False
        logging.info(f"[BinanceBroker] 초기화: market={self.market_type}, testnet={self.is_testnet}, url={self.base_url}")

    def _sign(self, params):
        """HMAC SHA256 서명 생성"""
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _get_headers(self):
        """기본 헤더 구성"""
        return {
            "X-MBX-APIKEY": self.api_key,
            "Content-Type": "application/json"
        }

    def _get_timestamp(self):
        """서버 타임스탬프 (밀리초)"""
        return int(time.time() * 1000)

    def _get_account_url(self):
        """시장 유형에 맞는 계정 조회 URL"""
        if self.market_type == "FUTURES":
            return f"{self.base_url}/fapi/v2/account"
        else:
            return f"{self.base_url}/api/v3/account"

    def _get_order_url(self):
        """시장 유형에 맞는 주문 URL"""
        if self.market_type == "FUTURES":
            return f"{self.base_url}/fapi/v1/order"
        else:
            return f"{self.base_url}/api/v3/order"

    def _get_open_orders_url(self):
        """시장 유형에 맞는 미체결 주문 URL"""
        if self.market_type == "FUTURES":
            return f"{self.base_url}/fapi/v1/openOrders"
        else:
            return f"{self.base_url}/api/v3/openOrders"

    def _get_ticker_url(self):
        """현재가 조회 URL"""
        if self.market_type == "FUTURES":
            return f"{self.base_url}/fapi/v1/ticker/price"
        else:
            return f"{self.base_url}/api/v3/ticker/price"

    def _get_time_url(self):
        """서버 시간 확인 URL"""
        if self.market_type == "FUTURES":
            return f"{self.base_url}/fapi/v1/time"
        else:
            return f"{self.base_url}/api/v3/time"

    def auth(self):
        """API 연결 테스트 (계정 정보 조회만 수행 — rate limit 절약)"""
        if not self.api_key or not self.api_secret:
            logging.error("Binance API Key or Secret is missing.")
            return False

        try:
            # 계정 정보 조회 1회만 (서버 시간 확인 제거 — 불필요한 request weight 소모 방지)
            params = {
                "timestamp": self._get_timestamp(),
                "recvWindow": 10000
            }
            params["signature"] = self._sign(params)

            res = requests.get(
                self._get_account_url(),
                headers=self._get_headers(),
                params=params,
                timeout=10
            )

            if res.status_code == 200:
                data = res.json()
                # FUTURES: "assets" 키, SPOT: "balances" 키
                if "assets" in data or "balances" in data:
                    self.connected = True
                    logging.info(f"[BinanceBroker] 인증 성공 ({self.market_type}, {'테스트넷' if self.is_testnet else '메인넷'})")
                    return True
                else:
                    logging.error(f"Binance Auth unexpected response keys: {list(data.keys())}")
                    return False
            else:
                error_data = {}
                try:
                    error_data = res.json()
                except:
                    pass
                code = error_data.get('code', '')
                msg = error_data.get('msg', res.text)
                if res.status_code == 418:
                    logging.error(f"Binance IP 밴 (rate limit 초과): {msg}")
                elif res.status_code == 429:
                    logging.error(f"Binance Rate Limit 초과 (잠시 후 재시도): {msg}")
                else:
                    logging.error(f"Binance Auth Failed [{res.status_code}] code={code}: {msg}")
                return False
        except Exception as e:
            logging.error(f"Binance Auth Exception: {e}")
            return False

    def get_balance(self):
        """잔고 조회 (USDT 기준 + 보유 코인 목록)"""
        if not self.api_key or not self.api_secret:
            logging.error("Binance API Key or Secret is missing.")
            return None

        try:
            params = {
                "timestamp": self._get_timestamp(),
                "recvWindow": 10000
            }
            params["signature"] = self._sign(params)

            res = requests.get(
                self._get_account_url(),
                headers=self._get_headers(),
                params=params,
                timeout=10
            )

            if res.status_code == 200:
                data = res.json()
                
                if self.market_type == "FUTURES":
                    return self._parse_futures_balance(data)
                else:
                    return self._parse_spot_balance(data)
            else:
                error_data = {}
                try:
                    error_data = res.json()
                except:
                    pass
                logging.error(f"Binance Balance Error: {error_data.get('msg', res.text)}")
                return None
        except Exception as e:
            logging.error(f"Binance Balance Exception: {e}")
            return None

    def _parse_futures_balance(self, data):
        """선물 계정 잔고 파싱"""
        assets = data.get("assets", [])
        positions = data.get("positions", [])

        usdt_balance = 0.0
        holdings = []

        # 자산(지갑) 잔고
        for a in assets:
            asset_name = a.get("asset", "")
            wallet_bal = float(a.get("walletBalance", 0))
            if asset_name == "USDT":
                usdt_balance = wallet_bal

        # 활성 포지션 목록 먼저 수집
        active_positions = [p for p in positions if float(p.get("positionAmt", 0)) != 0]

        # 현재가 일괄 조회 (1회 요청으로 전체 — rate limit 절약)
        symbols = {p.get("symbol", "") for p in active_positions}
        price_map = self._get_prices_bulk(symbols) if symbols else {}

        for p in active_positions:
            symbol = p.get("symbol", "")
            pos_amt = float(p.get("positionAmt", 0))
            entry_price = float(p.get("entryPrice", 0))
            unrealized_pnl = float(p.get("unrealizedProfit", 0))
            current_price = price_map.get(symbol, 0.0)

            holdings.append({
                "ticker": symbol,
                "name": symbol.replace("USDT", ""),
                "qty": abs(pos_amt),
                "side": "LONG" if pos_amt > 0 else "SHORT",
                "current_price": current_price,
                "avg_price": entry_price,
                "profit": unrealized_pnl,
                "value_usdt": abs(pos_amt) * current_price if current_price else 0,
                "ratio": (unrealized_pnl / (abs(pos_amt) * entry_price) * 100) if entry_price and pos_amt else 0
            })

        total_balance = float(data.get("totalWalletBalance", usdt_balance))

        return {
            "balance": total_balance,
            "available": float(data.get("availableBalance", 0)),
            "holdings": holdings,
            "acc_no": "BINANCE-FUTURES"
        }

    def _parse_spot_balance(self, data):
        """현물 계정 잔고 파싱"""
        balances = data.get("balances", [])

        usdt_balance = 0.0
        asset_rows = []

        for b in balances:
            asset = b.get("asset", "")
            free = float(b.get("free", 0))
            locked = float(b.get("locked", 0))
            total = free + locked

            if asset == "USDT":
                usdt_balance = total
            elif total > 0 and asset not in ["USDT", "BUSD", "USD"]:
                asset_rows.append({"asset": asset, "free": free, "locked": locked, "total": total})

        # 현재가 일괄 조회 (1회 요청으로 전체 — rate limit 절약)
        symbols = {f"{row['asset']}USDT" for row in asset_rows}
        price_map = self._get_prices_bulk(symbols) if symbols else {}

        holdings = []
        for row in asset_rows:
            symbol = f"{row['asset']}USDT"
            current_price = price_map.get(symbol, 0.0)
            holdings.append({
                "ticker": symbol,
                "name": row["asset"],
                "qty": row["total"],
                "free": row["free"],
                "locked": row["locked"],
                "current_price": current_price,
                "value_usdt": row["total"] * current_price if current_price else 0,
                "avg_price": 0,
                "profit": 0,
                "ratio": 0
            })

        return {
            "balance": usdt_balance,
            "holdings": holdings,
            "acc_no": "BINANCE"
        }

    def _get_prices_bulk(self, symbols):
        """여러 심볼의 현재가를 1회 요청으로 일괄 조회 (rate limit 절약)"""
        if not symbols:
            return {}
        try:
            res = requests.get(self._get_ticker_url(), timeout=5)
            if res.status_code == 200:
                all_prices = res.json()
                return {item["symbol"]: float(item["price"]) for item in all_prices if item["symbol"] in symbols}
        except Exception as e:
            logging.debug(f"Bulk price fetch failed: {e}")
        return {}

    def _get_current_price(self, symbol):
        """특정 심볼의 현재가 조회"""
        try:
            res = requests.get(
                self._get_ticker_url(),
                params={"symbol": symbol},
                timeout=5
            )
            if res.status_code == 200:
                return float(res.json().get("price", 0))
        except Exception as e:
            logging.debug(f"Price fetch failed for {symbol}: {e}")
        return 0.0

    def order(self, symbol, qty, price=None, side="BUY", order_type="MARKET"):
        """
        주문 실행
        - symbol: 거래 심볼 (예: BTCUSDT)
        - qty: 수량
        - price: 지정가 (LIMIT 주문시), MARKET이면 무시
        - side: BUY / SELL
        - order_type: MARKET / LIMIT
        """
        if not self.api_key or not self.api_secret:
            logging.error("Binance API Key or Secret is missing.")
            return None

        try:
            params = {
                "symbol": symbol.upper(),
                "side": side.upper(),
                "type": order_type.upper(),
                "timestamp": self._get_timestamp(),
                "recvWindow": 10000
            }

            # str()은 작은 수에서 '1e-05' 같은 과학적 표기를 만들어 Binance가 거부함
            def fmt_num(v):
                return format(float(v), '.8f').rstrip('0').rstrip('.')

            if order_type.upper() == "MARKET":
                params["quantity"] = fmt_num(qty)
            elif order_type.upper() == "LIMIT":
                params["quantity"] = fmt_num(qty)
                params["price"] = fmt_num(price)
                params["timeInForce"] = "GTC"

            params["signature"] = self._sign(params)

            res = requests.post(
                self._get_order_url(),
                headers=self._get_headers(),
                params=params,
                timeout=10
            )

            if res.status_code == 200:
                data = res.json()
                logging.info(f"Binance Order Success: {symbol} {qty} {side} - OrderId: {data.get('orderId')}")
                return data
            else:
                error_data = {}
                try:
                    error_data = res.json()
                except:
                    pass
                logging.error(f"Binance Order Error: {error_data.get('msg', res.text)}")
                return None
        except Exception as e:
            logging.error(f"Binance Order Exception: {e}")
            return None

    def get_open_orders(self, symbol=None):
        """미체결 주문 조회"""
        try:
            params = {
                "timestamp": self._get_timestamp(),
                "recvWindow": 10000
            }
            if symbol:
                params["symbol"] = symbol.upper()
            params["signature"] = self._sign(params)

            res = requests.get(
                self._get_open_orders_url(),
                headers=self._get_headers(),
                params=params,
                timeout=10
            )

            if res.status_code == 200:
                return res.json()
            return []
        except Exception as e:
            logging.error(f"Binance Open Orders Exception: {e}")
            return []

    def cancel_order(self, symbol, order_id):
        """주문 취소"""
        try:
            params = {
                "symbol": symbol.upper(),
                "orderId": order_id,
                "timestamp": self._get_timestamp(),
                "recvWindow": 10000
            }
            params["signature"] = self._sign(params)

            res = requests.delete(
                self._get_order_url(),
                headers=self._get_headers(),
                params=params,
                timeout=10
            )

            if res.status_code == 200:
                return res.json()
            return None
        except Exception as e:
            logging.error(f"Binance Cancel Order Exception: {e}")
            return None

    def get_exchange_info(self, symbol=None):
        """거래소 정보 조회 (거래 가능 심볼, 최소 주문량 등)"""
        try:
            if self.market_type == "FUTURES":
                url = f"{self.base_url}/fapi/v1/exchangeInfo"
            else:
                url = f"{self.base_url}/api/v3/exchangeInfo"
            
            params = {}
            if symbol:
                params["symbol"] = symbol.upper()
            res = requests.get(url, params=params, timeout=10)
            if res.status_code == 200:
                return res.json()
            return None
        except Exception as e:
            logging.error(f"Binance Exchange Info Exception: {e}")
            return None

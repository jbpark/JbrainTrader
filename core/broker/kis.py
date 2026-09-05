import requests
import json
import logging
import os
import time
from datetime import datetime

class KISBroker:
    """
    한국투자증권 (Korea Investment Securities) REST API Broker
    64-bit 환경에서 직접 실행 가능
    """
    def __init__(self, key=None, secret=None, acc_no=None, is_mock=True):
        self.key = key or os.getenv("KIS_APP_KEY")
        self.secret = secret or os.getenv("KIS_APP_SECRET")
        self.acc_no = acc_no or os.getenv("KIS_ACC_NO") # 12345678-01 형식 또는 8자리~10자리
        self.is_mock = is_mock
        
        # 실전/모의 서버 주소 구분
        self.base_url = "https://openapivts.koreainvestment.com:29443" if self.is_mock else "https://openapi.koreainvestment.com:9443"
        
        self.token = None
        self.token_expiry = None

    def _get_headers(self, tr_id=None, extra_headers=None):
        """기본 헤더 구성"""
        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.token}",
            "appkey": self.key,
            "appsecret": self.secret,
        }
        if tr_id:
            headers["tr_id"] = tr_id
        if extra_headers:
            headers.update(extra_headers)
        return headers

    def auth(self):
        """접근 토큰 발급"""
        if not self.key or not self.secret:
            logging.error("KIS AppKey or AppSecret is missing.")
            return False
            
        url = f"{self.base_url}/oauth2/tokenP"
        payload = {
            "grant_type": "client_credentials",
            "appkey": self.key,
            "appsecret": self.secret
        }
        
        try:
            res = requests.post(url, data=json.dumps(payload), timeout=10)
            if res.status_code == 200:
                data = res.json()
                self.token = data.get("access_token")
                # access_token_token_expired는 보통 24시간
                self.token_expiry = data.get("access_token_token_expired")
                logging.info("KIS API Token issued successfully.")
                return True
            else:
                logging.error(f"KIS Auth Failed: {res.status_code} {res.text}")
                return False
        except Exception as e:
            logging.error(f"KIS Auth Exception: {e}")
            return False

    def _is_token_valid(self):
        """토큰 존재 및 만료 여부 확인 (만료 10분 전부터 갱신 대상)"""
        if not self.token:
            return False
        if not self.token_expiry:
            return True
        try:
            expiry = datetime.strptime(str(self.token_expiry), "%Y-%m-%d %H:%M:%S")
            return (expiry - datetime.now()).total_seconds() > 600
        except Exception:
            return True

    def _ensure_token(self):
        """토큰이 없거나 만료 임박이면 재발급 (KIS 토큰은 24시간 만료 — 장기 실행 대응)"""
        if self._is_token_valid():
            return True
        logging.info("KIS token missing or expiring. Re-authenticating...")
        return self.auth()

    def get_account_list(self):
        """계좌 목록 조회 (계좌번호 자동화를 위함)"""
        if not self._ensure_token(): return []
            
        # 1차 시도: inquire-account-info
        res_list = self._fetch_account_list("/uapi/domestic-stock/v1/trading/inquire-account-info")
        if res_list: return res_list
            
        # 2차 시도: inquire-account-balance
        logging.info("Attempting fallback path 1 for account list...")
        res_list = self._fetch_account_list("/uapi/domestic-stock/v1/trading/inquire-account-balance")
        if res_list: return res_list

        # 3차 시도: inquire-account-list (일부 환경용)
        logging.info("Attempting fallback path 2 for account list...")
        return self._fetch_account_list("/uapi/domestic-stock/v1/trading/inquire-account-list")

    def _fetch_account_list(self, path):
        tr_id = "CTRP6010R" 
        url = f"{self.base_url}{path}"
        headers = self._get_headers(tr_id=tr_id, extra_headers={"custtype": "P"})
        params = {"CTX_AREA_FK100": "", "CTX_AREA_NK100": ""}
        
        try:
            res = requests.get(url, headers=headers, params=params, timeout=10)
            logging.info(f"KIS Account List ({path}) Status: {res.status_code}")
            if res.status_code == 200:
                data = res.json()
                if data.get("rt_cd") == "0":
                    accounts = data.get("output", [])
                    res_list = []
                    for acc in accounts:
                        acc_no = acc.get("cano")
                        if acc_no:
                            full_acc = f"{acc_no}-{acc.get('acnt_prdt_cd', '01')}"
                            res_list.append({
                                "acc_no": full_acc,
                                "name": acc.get("prdt_name", "주식계좌"),
                                "type": acc.get("acnt_dvsn_name")
                            })
                    return res_list
                else:
                    logging.error(f"KIS Account List Error: {data.get('msg1')}")
            return []
        except Exception as e:
            logging.error(f"KIS Account List Exception: {e}")
            return []

    def get_balance(self):
        """주식 잔고/예수금 조회"""
        if not self._ensure_token(): return None

        if not self.acc_no:
            # 계좌번호가 없으면 자동으로 첫 번째 계좌 가져오기
            accs = self.get_account_list()
            if accs:
                self.acc_no = accs[0]["acc_no"]
                logging.info(f"KIS Auto-selected Account: {self.acc_no}")
            else:
                logging.error("KIS Account Number is missing and auto-fetch failed.")
                return None
            
        # 국내 주식 잔고 조회 TR
        tr_id = "VTTC8434R" if self.is_mock else "TTTC8434R"
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-balance"
        
        # 계좌번호 분리 (앞 8자리, 뒤 2자리)
        temp_acc = self.acc_no.replace("-", "")
        acc_main = temp_acc[:8]
        acc_sub = temp_acc[8:] if len(temp_acc) > 8 else "01"

        params = {
            "CANO": acc_main,
            "ACNT_PRDT_CD": acc_sub,
            "AFHR_FLPR_YN": "N",
            "O_PRC_VRTN_YN": "N",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "00",
            "OFL_YN": "N",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": ""
        }
        
        headers = self._get_headers(tr_id=tr_id)
        
        try:
            res = requests.get(url, headers=headers, params=params, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if data.get("rt_cd") == "0":
                    summary = data.get("output2", [{}])[0]
                    balance = int(summary.get("dnca_tot_amt", 0))
                    holdings = data.get("output1", [])
                    
                    parsed_holdings = []
                    for h in holdings:
                        qty = int(h.get("hldg_qty", 0))
                        if qty > 0:
                            parsed_holdings.append({
                                "ticker": h.get("pdno"),
                                "name": h.get("prdt_name"),
                                "qty": qty,
                                "price": int(h.get("prpr", 0)),
                                "current_price": int(h.get("prpr", 0)),
                                "avg_price": float(h.get("pchs_avg_pric", 0)),
                                "buy_price": float(h.get("pchs_avg_pric", 0)),
                                "profit": int(h.get("evlu_pfls_amt", 0)),
                                "ratio": float(h.get("evlu_pfls_rt", 0))
                            })
                    
                    return {"balance": balance, "holdings": parsed_holdings, "acc_no": self.acc_no}
                else:
                    msg = data.get('rt_cd', '') + " : " + data.get('msg1', '')
                    logging.error(f"KIS Balance Error: {msg}")
                    
                    # [핵심] 계좌번호 오류 시 01 접미사로 한 번 더 시도
                    if ("INVALID_CHECK_ACNO" in msg or "계좌번호" in msg) and acc_sub != "01":
                        logging.info(f"Retrying with suffix '01' instead of '{acc_sub}'...")
                        original_acc = self.acc_no
                        temp_main = temp_acc[:8]
                        self.acc_no = f"{temp_main}-01"
                        result = self.get_balance()
                        if not result: # 실패하면 원복
                            self.acc_no = original_acc
                        return result
                    
                    # 계좌 목록 재조회 시도
                    if "INVALID_CHECK_ACNO" in msg or "계좌번호" in msg:
                        logging.info("Attempting to re-fetch account list due to account error...")
                        accs = self.get_account_list()
                        if accs:
                            self.acc_no = accs[0]["acc_no"]
                            logging.info(f"Re-selected KIS Account: {self.acc_no}. Please retry.")
            return None
        except Exception as e:
            logging.error(f"KIS Balance Exception: {e}")
            return None

    def order(self, ticker, qty, price, side="BUY", ord_dvsn=None):
        """주식 주문 (현금). ord_dvsn: "00"(지정가) / "01"(시장가, 기본값)"""
        if not self._ensure_token(): return None
            
        if not self.acc_no:
            # 계좌번호 자동 조회 시도
            accs = self.get_account_list()
            if accs: self.acc_no = accs[0]["acc_no"]
            else: return None

        # tr_id: VTTC0802U(매수), VTTC0801U(매도) - 모의
        # tr_id: TTTC0802U(매수), TTTC0801U(매도) - 실전
        if side == "BUY":
            tr_id = "VTTC0802U" if self.is_mock else "TTTC0802U"
        else:
            tr_id = "VTTC0801U" if self.is_mock else "TTTC0801U"
            
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash"
        
        temp_acc = self.acc_no.replace("-", "")
        acc_main = temp_acc[:8]
        acc_sub = temp_acc[8:] if len(temp_acc) > 8 else "01"

        # KIS 스펙상 시장가(01) 주문은 ORD_UNPR을 반드시 "0"으로 전송해야 함
        # (기존 코드는 시장가에 단가를 실어 보내 주문 거부 위험이 있었음)
        if ord_dvsn is None:
            ord_dvsn = "01"
        ord_unpr = str(int(price)) if (ord_dvsn == "00" and price and price > 0) else "0"

        payload = {
            "CANO": acc_main,
            "ACNT_PRDT_CD": acc_sub,
            "PDNO": ticker,
            "ORD_DVSN": ord_dvsn, # 00: 지정가, 01: 시장가
            "ORD_QTY": str(int(qty)),
            "ORD_UNPR": ord_unpr
        }
        
        headers = self._get_headers(tr_id=tr_id)
        
        try:
            res = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
            if res.status_code == 200:
                data = res.json()
                if data.get("rt_cd") == "0":
                    logging.info(f"KIS Order Success: {ticker} {qty} {side}")
                else:
                    logging.error(f"KIS Order Error: {data.get('msg1')}")
                return data
            return None
        except Exception as e:
            logging.error(f"KIS Order Exception: {e}")
            return None

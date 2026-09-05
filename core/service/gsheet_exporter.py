# -*- coding: utf-8 -*-
"""매매일지 구글 시트 업로드

설정 (.env):
  GSHEET_CREDENTIALS_PATH        : 구글 서비스 계정 키(JSON) 파일 경로
  GSHEET_SPREADSHEET_ID          : 업로드 대상 스프레드시트 ID (URL의 /d/와 /edit 사이 문자열)
  GSHEET_SPREADSHEET_ID_OVERSEAS : (선택) 해외 주식용 스프레드시트 ID —
                                   계좌가 '해외' 모드일 때 매매일지/보유종목이 이 시트로 업로드됨

사전 준비:
  1. Google Cloud Console에서 서비스 계정 생성 + JSON 키 다운로드
  2. Google Sheets API 사용 설정
  3. 대상 스프레드시트를 서비스 계정 이메일(...@...iam.gserviceaccount.com)과 편집자로 공유
"""
import os
import re
import logging


class GSheetConfigError(Exception):
    """구글 시트 설정 누락/오류"""


TRADE_HEADERS = ["날짜", "종목코드", "종목명", "수량",
                 "매수단가", "매도단가", "매수금액", "매도금액",
                 "수수료", "세금", "실현손익", "수익률(%)", "계좌"]
SUMMARY_HEADERS = ["날짜", "매매종목수", "총매수금액", "총매도금액",
                   "수수료", "세금", "실현손익(정산)", "계좌"]
SUMMARY_SHEET_NAME = "일별요약"


def _num(v):
    """Decimal/None → 숫자 (gspread 직렬화 안전)"""
    if v is None:
        return 0
    try:
        f = float(v)
        return int(f) if f == int(f) else round(f, 4)
    except (TypeError, ValueError):
        return 0


def _num_or_blank(v):
    """숫자로 변환하되, 값이 없으면 빈 칸 (0으로 오해되지 않도록)"""
    if v is None or v == "":
        return ""
    try:
        f = float(str(v).replace(",", ""))
        return int(f) if f == int(f) else round(f, 4)
    except (TypeError, ValueError):
        return ""


# ── AI 종목 상세 비교 ──
COMPARE_HEADERS = [
    "종목명", "종목코드", "시장", "주가", "시가총액(억)", "PER", "PBR", "ROE(%)",
    "매출(억)", "영업이익(억)", "순이익(억)", "영업이익률(%)", "부채비율(%)",
    "매출성장(%)", "배당(%)", "외국인(%)", "52주 최고", "52주 최저", "총평", "기준일시",
]
# (헤더 인덱스에 대응하는 데이터 키) — 숫자 컬럼만
COMPARE_NUM_KEYS = [
    "price", "market_cap", "per", "pbr", "roe", "revenue", "operating_profit",
    "net_income", "operating_margin", "debt_ratio", "revenue_growth",
    "dividend_yield", "foreign_ownership", "week52_high", "week52_low",
]

# ── AI 매매 전략 ──
STRATEGY_HEADERS = [
    "종목명", "종목코드", "시장", "현재가", "진입가", "목표가", "손절가",
    "기대수익", "위험도", "비중", "보유기간", "요약",
    "매수조건", "매도조건", "리스크", "근거", "기준일시",
]

# ── 보유 종목 ──
HOLDINGS_SHEET_NAME = "보유종목"
HOLDINGS_HEADERS = [
    "종목명", "종목코드", "보유수량", "매입단가", "매입금액",
    "현재가", "평가금액", "평가손익", "수익률(%)",
    "진입가격대", "목표가", "손절가", "기대수익", "투자비중", "보유기간",
    "계좌", "기준일시",
]

# ── AI 전략 성과 (스코어카드) ──
SCORECARD_SHEET_NAME = "전략성과"
SCORECARD_SUMMARY_SHEET_NAME = "전략성과요약"
SCORECARD_HEADERS = [
    "종목명", "종목코드", "프로파일", "모델", "분석일시",
    "기준가", "목표가", "손절가", "판정", "판정일", "판정가",
    "실현수익률(%)", "미실현수익률(%)", "기대수익", "보유기간", "만료일",
    "비고", "채점일시",
]
SCORECARD_SUMMARY_HEADERS = [
    "구분", "이름", "전략수", "목표달성", "손절도달", "기간만료", "진행중",
    "적중률(%)", "평균수익률(%)", "진행중평균(%)",
]

# ── AI 매매일지 복기 ──
REVIEW_SHEET_NAME = "AI복기"
REVIEW_HEADERS = [
    "기간", "총평", "매매 점수", "반복 패턴", "전략 이행 분석",
    "다음 주 체크포인트", "모델", "생성일시",
]

# 구글 시트 탭 이름에 쓸 수 없는 문자
_INVALID_SHEET_CHARS = r'[:\\/?*\[\]]'


def sanitize_sheet_name(name, fallback="비교"):
    """프로파일명을 구글 시트 탭 이름으로 사용 가능하게 정리 (최대 100자)"""
    s = re.sub(_INVALID_SHEET_CHARS, "_", str(name or "")).strip()
    return (s[:100] or fallback)


def _col_letter(n):
    """1-based 컬럼 번호 -> 시트 컬럼 문자 (1 -> A, 27 -> AA)"""
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(ord("A") + r) + s
    return s


def _join_list(v):
    """문자열 배열 → 셀 안에서 줄바꿈으로 구분된 하나의 문자열"""
    if isinstance(v, (list, tuple)):
        return "\n".join(str(x) for x in v if str(x).strip())
    return str(v or "")


class GSheetExporter:
    def __init__(self, market="DOMESTIC"):
        """market='OVERSEAS'면 해외 주식용 스프레드시트(GSHEET_SPREADSHEET_ID_OVERSEAS)에 업로드"""
        cred_path = os.getenv("GSHEET_CREDENTIALS_PATH", "").strip()
        if str(market or "").upper() == "OVERSEAS":
            self.spreadsheet_id = os.getenv("GSHEET_SPREADSHEET_ID_OVERSEAS", "").strip()
            if not self.spreadsheet_id:
                raise GSheetConfigError(
                    "해외 주식용 스프레드시트가 설정되지 않았습니다. .env에 "
                    "GSHEET_SPREADSHEET_ID_OVERSEAS(해외용 스프레드시트 ID)를 추가하고 "
                    "해당 시트를 서비스 계정과 공유한 뒤 백엔드를 재시작하세요.")
        else:
            self.spreadsheet_id = os.getenv("GSHEET_SPREADSHEET_ID", "").strip()
        if not cred_path or not self.spreadsheet_id:
            raise GSheetConfigError(
                "구글 시트 설정이 없습니다. .env에 GSHEET_CREDENTIALS_PATH(서비스 계정 키 JSON 경로)와 "
                "GSHEET_SPREADSHEET_ID를 추가한 뒤 백엔드를 재시작하세요. "
                "자세한 방법은 docs/guide/구글시트_매매일지_설정.md 참고.")
        if not os.path.isfile(cred_path):
            raise GSheetConfigError(f"서비스 계정 키 파일을 찾을 수 없습니다: {cred_path}")

        try:
            import gspread
            from google.oauth2.service_account import Credentials
        except ImportError:
            raise GSheetConfigError(
                "gspread 패키지가 없습니다. 백엔드 파이썬에 설치하세요: "
                "pip install gspread google-auth")

        creds = Credentials.from_service_account_file(
            cred_path, scopes=["https://www.googleapis.com/auth/spreadsheets"])
        self.gc = gspread.authorize(creds)

    @staticmethod
    def _read_rows(ws):
        """기존 행 읽기 — 반드시 서식이 적용되지 않은 원래 값으로 읽는다.

        get_all_values()는 "74,257"처럼 서식이 적용된 문자열을 돌려주는데,
        이것을 RAW로 다시 쓰면 숫자가 텍스트로 바뀌어 정렬과 합계가 깨진다.
        """
        try:
            return ws.get_values(value_render_option="UNFORMATTED_VALUE")
        except Exception:
            return ws.get_all_values()

    @staticmethod
    def _apply_header_sort(ws, headers, row_count):
        """헤더 행 고정 + 필터 적용 → 컬럼명 드롭다운으로 정렬/필터 가능.

        재업로드 때마다 데이터 범위가 달라지므로 기존 필터를 지우고 다시 건다.
        (호출 전에 ws.clear_basic_filter()로 먼저 지워둔 뒤 데이터를 쓴다.)
        """
        if row_count < 1:
            return
        try:
            ws.freeze(rows=1)
            ws.set_basic_filter(f"A1:{_col_letter(len(headers))}{row_count}")
        except Exception as e:  # 필터 설정 실패가 업로드 자체를 막지는 않도록
            logging.warning(f"[GSheet] 헤더 정렬 설정 실패({ws.title}): {e}")

    def _get_or_create_ws(self, sh, name, headers, cols=20):
        try:
            ws = sh.worksheet(name)
        except Exception:
            ws = sh.add_worksheet(title=name, rows=200, cols=cols)
            ws.append_row(headers)
        # 헤더가 비어 있으면 채움
        if not ws.row_values(1):
            ws.append_row(headers)
        return ws

    @staticmethod
    def _aggregate_by_ticker(trades):
        """종목별 합산 (웹 매매일지의 '종목별 (합산)' 모드와 동일한 로직)"""
        has_summary = {str(t.get("ticker")) for t in trades if str(t.get("side")) == "SUMMARY"}
        groups = {}
        for t in trades:
            side = str(t.get("side") or "")
            ticker = str(t.get("ticker") or "")
            # 해당 종목에 SUMMARY가 있으면 BUY/SELL 개별 행은 건너뜀 (중복 방지)
            if ticker in has_summary and side in ("BUY", "SELL"):
                continue

            g = groups.setdefault(ticker, {
                "ticker": ticker,
                "ticker_name": str(t.get("ticker_name") or ""),
                "buy_amount": 0, "sell_amount": 0,
                "buy_qty": 0, "sell_qty": 0,
                "profit": 0, "fee": 0, "tax": 0,
                "acc_no": str(t.get("acc_no") or ""),
                "seen": set(),
            })
            key = t.get("order_no") or f"{ticker}_{side}_{t.get('execution_time')}"
            if key in g["seen"]:
                continue
            g["seen"].add(key)

            qty = _num(t.get("qty"))
            if side in ("SUMMARY", "BUY"):
                b_amt = _num(t.get("buy_amount")) or (_num(t.get("amount")) if side == "BUY" else 0)
                g["buy_amount"] += b_amt
                g["buy_qty"] += qty
            if side in ("SUMMARY", "SELL"):
                g["sell_amount"] += _num(t.get("amount"))
                g["sell_qty"] += qty
            g["profit"] += _num(t.get("profit"))
            g["fee"] += _num(t.get("fee"))
            g["tax"] += _num(t.get("tax"))

        results = []
        for g in groups.values():
            if abs(g["profit"]) == 0:
                continue
            g["qty"] = g["sell_qty"] or g["buy_qty"]
            g["buy_price"] = round(g["buy_amount"] / g["buy_qty"]) if g["buy_qty"] else 0
            g["sell_price"] = round(g["sell_amount"] / g["sell_qty"]) if g["sell_qty"] else 0
            g["profit_rate"] = round(g["profit"] / g["buy_amount"] * 100, 2) if g["buy_amount"] else 0
            results.append(g)
        return sorted(results, key=lambda g: g["ticker_name"])

    def export_daily(self, db, date_str, acc_no=None):
        """특정 날짜의 매매 내역(종목별 합산)과 정산 손익을 스프레드시트에 업로드 (재실행 시 해당 날짜 덮어씀)"""
        trades = db.get_trades_by_date(date_str, acc_no=acc_no)
        total = db.get_daily_profit_total(date_str, acc_no=acc_no)

        if not trades and not total:
            return {"rows": 0, "message": "업로드할 매매 내역이 없습니다.",
                    "url": f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}"}

        sh = self.gc.open_by_key(self.spreadsheet_id)

        # ── 1) 월별 매매내역 탭 (YYYY-MM): 해당 날짜 행을 지우고 종목별 합산으로 다시 씀 ──
        ws_name = date_str[:7]
        ws = self._get_or_create_ws(sh, ws_name, TRADE_HEADERS)
        existing = self._read_rows(ws)
        header = TRADE_HEADERS  # 헤더는 항상 최신 형식으로 갱신
        kept = [r for r in existing[1:] if r and r[0] != date_str]

        new_rows = []
        for g in self._aggregate_by_ticker(trades):
            new_rows.append([
                date_str,
                g["ticker"],
                g["ticker_name"],
                g["qty"],
                g["buy_price"],
                g["sell_price"],
                g["buy_amount"],
                g["sell_amount"],
                g["fee"],
                g["tax"],
                g["profit"],
                g["profit_rate"],
                g["acc_no"] or str(acc_no or ""),
            ])

        all_rows = [header] + sorted(kept + new_rows, key=lambda r: (str(r[0]), str(r[2])))
        ws.clear_basic_filter()
        ws.clear()
        # RAW 입력: 종목코드("005930")가 숫자로 변환되어 앞자리 0이 사라지는 것을 방지
        ws.update(all_rows, "A1", value_input_option="RAW")
        # 금액 컬럼 천 단위 구분 서식 (D:K), 수익률은 소수 2자리 (L)
        ws.format("D2:K", {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}})
        ws.format("L2:L", {"numberFormat": {"type": "NUMBER", "pattern": "0.00"}})
        self._apply_header_sort(ws, TRADE_HEADERS, len(all_rows))

        # ── 2) 일별요약 탭: 날짜(+계좌) 기준 upsert ──
        if total:
            ws2 = self._get_or_create_ws(sh, SUMMARY_SHEET_NAME, SUMMARY_HEADERS, cols=10)
            existing2 = self._read_rows(ws2)
            header2 = SUMMARY_HEADERS  # 헤더는 항상 최신 형식으로 갱신
            kept2 = [r for r in existing2[1:] if r and r[0] != date_str]
            summary_row = [
                date_str,
                len(new_rows),  # 종목별 합산 기준 매매 종목 수
                _num(total.get("buy_amount")),
                _num(total.get("sell_amount")),
                _num(total.get("fee")),
                _num(total.get("tax")),
                _num(total.get("profit")),
                str(total.get("acc_no") or acc_no or ""),
            ]
            all2 = [header2] + sorted(kept2 + [summary_row], key=lambda r: str(r[0]))
            ws2.clear_basic_filter()
            ws2.clear()
            ws2.update(all2, "A1", value_input_option="RAW")
            ws2.format("B2:G", {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}})
            self._apply_header_sort(ws2, SUMMARY_HEADERS, len(all2))

        logging.info(f"[GSheet] {date_str} 매매일지 업로드 완료: 매매 {len(new_rows)}건")
        return {"rows": len(new_rows),
                "url": f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}"}

    def export_comparison(self, profile_name, rows, finished_at=None):
        """AI 종목 상세 비교 결과를 프로파일명 탭에 업로드 (매번 최신 내용으로 덮어씀)"""
        if not rows:
            return {"rows": 0, "message": "업로드할 비교 결과가 없습니다.",
                    "url": f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}"}

        sheet_name = sanitize_sheet_name(profile_name)
        sh = self.gc.open_by_key(self.spreadsheet_id)
        ws = self._get_or_create_ws(sh, sheet_name, COMPARE_HEADERS, cols=len(COMPARE_HEADERS) + 2)

        data = [COMPARE_HEADERS]
        for c in rows:
            if not isinstance(c, dict):
                continue
            data.append([
                str(c.get("name") or ""),
                str(c.get("ticker") or ""),
                str(c.get("market") or ""),
                *[_num_or_blank(c.get(k)) for k in COMPARE_NUM_KEYS],
                str(c.get("comment") or ""),
                str(finished_at or ""),
            ])

        ws.clear_basic_filter()
        ws.clear()
        # RAW: 종목코드("005930")가 숫자로 변환돼 앞자리 0이 사라지는 것을 방지
        ws.update(data, "A1", value_input_option="RAW")
        # 금액 컬럼은 정수, 비율/배수 컬럼은 소수 2자리
        # (#,##0.## 는 구글 시트에서 정수도 "274,500." 처럼 점이 남아 컬럼을 나눔)
        int_fmt = {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}}
        dec_fmt = {"numberFormat": {"type": "NUMBER", "pattern": "#,##0.00"}}
        ws.batch_format([
            # 주가, 시가총액, 매출, 영업이익, 순이익, 52주 최고/최저
            {"range": "D2:E", "format": int_fmt},
            {"range": "I2:K", "format": int_fmt},
            {"range": "Q2:R", "format": int_fmt},
            # PER, PBR, ROE / 영업이익률, 부채비율, 매출성장, 배당, 외국인
            {"range": "F2:H", "format": dec_fmt},
            {"range": "L2:P", "format": dec_fmt},
        ])
        self._apply_header_sort(ws, COMPARE_HEADERS, len(data))

        logging.info(f"[GSheet] 상세 비교 업로드 완료: '{sheet_name}' {len(data) - 1}종목")
        return {"rows": len(data) - 1, "sheet": sheet_name,
                "url": f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}"}

    @staticmethod
    def _latest_strategy(entries):
        """같은 종목에 AI 매매 전략 분석이 여러 개면 가장 최근(finished_at) 것을 선택"""
        if not entries:
            return None
        best = max(entries, key=lambda e: str(e.get("finished_at") or ""))
        s = best.get("strategy")
        return s if isinstance(s, dict) else None

    def export_holdings(self, holdings, acc_no=None, snapshot_at=None, strategies=None):
        """현재 보유 종목을 '보유종목' 탭에 업로드 (스냅샷이므로 매번 전체 갱신)

        strategies: AI 매매 전략 분석 결과 {종목코드: [{finished_at, strategy, ...}, ...]}.
        분석이 있는 종목은 진입가격대/목표가/손절가/기대수익/투자비중/보유기간을 함께 기록한다.
        """
        if not holdings:
            return {"rows": 0, "message": "보유 중인 종목이 없습니다.",
                    "url": f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}"}

        sh = self.gc.open_by_key(self.spreadsheet_id)
        ws = self._get_or_create_ws(sh, HOLDINGS_SHEET_NAME, HOLDINGS_HEADERS,
                                    cols=len(HOLDINGS_HEADERS) + 2)

        strategies = strategies or {}

        data = [HOLDINGS_HEADERS]
        total_buy = total_eval = total_profit = 0
        for h in holdings:
            if not isinstance(h, dict):
                continue
            qty = _num(h.get("qty"))
            buy_price = _num(h.get("buy_price") or h.get("avg_price"))
            cur_price = _num(h.get("current_price"))
            buy_amount = round(buy_price * qty)
            eval_amount = round(cur_price * qty)
            profit = _num(h.get("profit"))
            # 서버 ratio(수수료·세금 반영)를 그대로 쓰고, 없으면 매입금액 기준으로 계산
            ratio = _num(h.get("ratio")) if h.get("ratio") is not None else (
                round(profit / buy_amount * 100, 2) if buy_amount else 0)

            total_buy += buy_amount
            total_eval += eval_amount
            total_profit += profit

            strat = self._latest_strategy(strategies.get(str(h.get("ticker") or "").strip()))
            if strat:
                strat_cols = [
                    str(strat.get("entry_price") or ""),
                    _num_or_blank(strat.get("target_price")),
                    _num_or_blank(strat.get("stop_loss")),
                    str(strat.get("expected_return") or ""),
                    str(strat.get("position_size") or ""),
                    str(strat.get("holding_period") or ""),
                ]
            else:
                strat_cols = [""] * 6

            data.append([
                str(h.get("name") or ""),
                str(h.get("ticker") or ""),
                qty, buy_price, buy_amount, cur_price, eval_amount,
                profit, ratio,
                *strat_cols,
                str(acc_no or ""),
                str(snapshot_at or ""),
            ])

        total_ratio = round(total_profit / total_buy * 100, 2) if total_buy else 0

        # 헤더 정렬(필터)을 쓰려면 합계 행이 없어야 한다. 합계 행이 있으면
        # 정렬 시 데이터 사이로 섞여버리므로 시트에는 종목 행만 쓴다.
        ws.clear_basic_filter()
        ws.clear()
        # RAW: 종목코드("005930")가 숫자로 변환돼 앞자리 0이 사라지는 것을 방지
        ws.update(data, "A1", value_input_option="RAW")
        ws.batch_format([
            # 보유수량 ~ 평가손익
            {"range": "C2:H", "format": {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}}},
            # 수익률
            {"range": "I2:I", "format": {"numberFormat": {"type": "NUMBER", "pattern": "0.00"}}},
            # 목표가, 손절가
            {"range": "K2:L", "format": {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}}},
        ])
        self._apply_header_sort(ws, HOLDINGS_HEADERS, len(data))

        rows = len(data) - 1  # 헤더 제외
        logging.info(f"[GSheet] 보유 종목 업로드 완료: {rows}종목")
        return {"rows": rows, "sheet": HOLDINGS_SHEET_NAME,
                "total_buy": total_buy, "total_profit": total_profit,
                "total_ratio": total_ratio,
                "url": f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}"}

    def export_scorecard(self, rows, stats, graded_at=None):
        """AI 전략 성과(스코어카드)를 '전략성과'/'전략성과요약' 탭에 업로드 (전체 갱신)"""
        if not rows:
            return {"rows": 0, "message": "업로드할 전략 성과가 없습니다.",
                    "url": f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}"}

        sh = self.gc.open_by_key(self.spreadsheet_id)

        # ── 1) 상세 탭 ──
        ws = self._get_or_create_ws(sh, SCORECARD_SHEET_NAME, SCORECARD_HEADERS,
                                    cols=len(SCORECARD_HEADERS) + 2)
        data = [SCORECARD_HEADERS]
        for r in rows:
            data.append([
                str(r.get("name") or ""),
                str(r.get("ticker") or ""),
                str(r.get("profile_name") or ""),
                str(r.get("model") or ""),
                str(r.get("analyzed_at") or ""),
                _num_or_blank(r.get("base_price")),
                _num_or_blank(r.get("target_price")),
                _num_or_blank(r.get("stop_loss")),
                str(r.get("outcome_label") or r.get("outcome") or ""),
                str(r.get("outcome_date") or ""),
                _num_or_blank(r.get("outcome_price")),
                _num_or_blank(r.get("realized_return")),
                _num_or_blank(r.get("unrealized_return")),
                str(r.get("expected_return") or ""),
                str(r.get("holding_period") or ""),
                str(r.get("deadline_date") or ""),
                str(r.get("note") or ""),
                str(r.get("graded_at") or graded_at or ""),
            ])
        ws.clear_basic_filter()
        ws.clear()
        ws.update(data, "A1", value_input_option="RAW")
        ws.batch_format([
            {"range": "F2:H", "format": {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}}},
            {"range": "K2:K", "format": {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}}},
            {"range": "L2:M", "format": {"numberFormat": {"type": "NUMBER", "pattern": "0.00"}}},
        ])
        self._apply_header_sort(ws, SCORECARD_HEADERS, len(data))

        # ── 2) 요약 탭 (프로파일별 + 모델별) ──
        ws2 = self._get_or_create_ws(sh, SCORECARD_SUMMARY_SHEET_NAME,
                                     SCORECARD_SUMMARY_HEADERS,
                                     cols=len(SCORECARD_SUMMARY_HEADERS) + 2)
        data2 = [SCORECARD_SUMMARY_HEADERS]
        for kind, key in (("프로파일", "by_profile"), ("모델", "by_model")):
            for name, s in sorted((stats.get(key) or {}).items()):
                data2.append([
                    kind, name, s.get("total", 0),
                    s.get("target_hit", 0), s.get("stop_hit", 0),
                    s.get("expired", 0), s.get("open", 0),
                    _num_or_blank(s.get("hit_rate")),
                    _num_or_blank(s.get("avg_return")),
                    _num_or_blank(s.get("avg_open_return")),
                ])
        ws2.clear_basic_filter()
        ws2.clear()
        ws2.update(data2, "A1", value_input_option="RAW")
        ws2.format("H2:J", {"numberFormat": {"type": "NUMBER", "pattern": "0.00"}})
        self._apply_header_sort(ws2, SCORECARD_SUMMARY_HEADERS, len(data2))

        logging.info(f"[GSheet] 전략 성과 업로드 완료: {len(data) - 1}건")
        return {"rows": len(data) - 1, "sheet": SCORECARD_SHEET_NAME,
                "url": f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}"}

    def export_review(self, period, report, model="", finished_at=None):
        """매매일지 AI 복기 리포트를 'AI복기' 탭에 추가 (같은 기간이면 갱신)"""
        if not isinstance(report, dict) or not report:
            return {"rows": 0, "message": "업로드할 복기 리포트가 없습니다.",
                    "url": f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}"}

        sh = self.gc.open_by_key(self.spreadsheet_id)
        ws = self._get_or_create_ws(sh, REVIEW_SHEET_NAME, REVIEW_HEADERS,
                                    cols=len(REVIEW_HEADERS) + 2)

        patterns = report.get("patterns") or []
        pattern_text = "\n".join(
            f"- {p.get('title')}: {p.get('detail')}" if isinstance(p, dict) else f"- {p}"
            for p in patterns)
        new_row = [
            str(period or ""),
            str(report.get("summary") or ""),
            _num_or_blank(report.get("score")),
            pattern_text,
            str(report.get("strategy_adherence") or ""),
            _join_list(report.get("checkpoints")),
            str(model or ""),
            str(finished_at or ""),
        ]

        existing = self._read_rows(ws)
        rows = [r for r in existing[1:] if any(str(c).strip() for c in r)]
        updated = False
        for i, r in enumerate(rows):
            if r and str(r[0]).strip() == str(period):
                rows[i] = new_row
                updated = True
                break
        if not updated:
            rows.append(new_row)
        rows.sort(key=lambda r: str(r[0]))

        ws.clear_basic_filter()
        ws.clear()
        ws.update([REVIEW_HEADERS] + rows, "A1", value_input_option="RAW")
        ws.format("B2:F", {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"})
        self._apply_header_sort(ws, REVIEW_HEADERS, len(rows) + 1)

        logging.info(f"[GSheet] AI 복기 업로드 완료: {period}")
        return {"rows": len(rows), "sheet": REVIEW_SHEET_NAME, "updated": updated,
                "url": f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}"}

    def export_strategy(self, profile_name, strategy, finished_at=None):
        """AI 매매 전략을 프로파일명 탭에 업로드.

        같은 탭에 이미 같은 종목코드 행이 있으면 그 행을 갱신하고,
        없으면 맨 아래에 새 행으로 추가한다 (종목별 전략 이력 누적).
        """
        if not isinstance(strategy, dict) or not strategy:
            return {"rows": 0, "message": "업로드할 매매 전략이 없습니다.",
                    "url": f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}"}

        ticker = str(strategy.get("ticker") or "").strip()
        sheet_name = sanitize_sheet_name(profile_name, fallback="매매전략")
        sh = self.gc.open_by_key(self.spreadsheet_id)
        ws = self._get_or_create_ws(sh, sheet_name, STRATEGY_HEADERS,
                                    cols=len(STRATEGY_HEADERS) + 2)

        existing = self._read_rows(ws)
        header = existing[0] if existing else []
        # 다른 종류의 데이터가 들어 있는 탭을 덮어쓰지 않도록 방어
        if header and header != STRATEGY_HEADERS and header[:3] == COMPARE_HEADERS[:3] \
                and len(header) >= len(COMPARE_HEADERS) - 2:
            raise GSheetConfigError(
                f"'{sheet_name}' 탭은 AI 종목 상세 비교가 사용 중입니다. "
                "AI 매매 프로파일 이름을 다르게 지정하세요.")

        new_row = [
            str(strategy.get("name") or ""),
            ticker,
            str(strategy.get("market") or ""),
            _num_or_blank(strategy.get("current_price")),
            str(strategy.get("entry_price") or ""),
            _num_or_blank(strategy.get("target_price")),
            _num_or_blank(strategy.get("stop_loss")),
            str(strategy.get("expected_return") or ""),
            str(strategy.get("risk_level") or ""),
            str(strategy.get("position_size") or ""),
            str(strategy.get("holding_period") or ""),
            str(strategy.get("summary") or ""),
            _join_list(strategy.get("buy_conditions")),
            _join_list(strategy.get("sell_conditions")),
            _join_list(strategy.get("risks")),
            str(strategy.get("reason") or ""),
            str(finished_at or ""),
        ]

        rows = [r for r in existing[1:] if any(str(c).strip() for c in r)]
        updated = False
        for i, r in enumerate(rows):
            if len(r) > 1 and str(r[1]).strip() == ticker and ticker:
                rows[i] = new_row
                updated = True
                break
        if not updated:
            rows.append(new_row)

        ws.clear_basic_filter()
        ws.clear()
        # RAW: 종목코드("005930")가 숫자로 변환돼 앞자리 0이 사라지는 것을 방지
        ws.update([STRATEGY_HEADERS] + rows, "A1", value_input_option="RAW")
        int_fmt = {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}}
        ws.batch_format([
            {"range": "D2:D", "format": int_fmt},   # 현재가
            {"range": "F2:G", "format": int_fmt},   # 목표가, 손절가
        ])
        # 조건/리스크는 줄바꿈이 보이도록 자동 줄바꿈
        ws.format("L2:P", {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"})
        self._apply_header_sort(ws, STRATEGY_HEADERS, len(rows) + 1)

        action = "갱신" if updated else "추가"
        logging.info(f"[GSheet] 매매 전략 {action}: '{sheet_name}' {strategy.get('name')}({ticker})")
        return {"rows": len(rows), "sheet": sheet_name, "ticker": ticker,
                "ticker_name": str(strategy.get("name") or ""), "updated": updated,
                "url": f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}"}

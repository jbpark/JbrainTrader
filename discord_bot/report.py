"""
report.py
=========
generate_report(symbol, action, ticker_data) → discord.Embed

action 값:
  "status"  - 종목 현재 상태
  "pnl"     - 실현 손익
  "detail"  - 보유수량, 평균단가, 전략 등 상세정보
"""

import discord
from datetime import datetime


# ─────────────────────────────────────────────
# 유틸리티
# ─────────────────────────────────────────────
def _fmt_price(value) -> str:
    try:
        return f"{int(float(value)):,}원"
    except (TypeError, ValueError):
        return "-"


def _fmt_profit(value) -> str:
    try:
        v = float(value)
        sign = "+" if v >= 0 else ""
        return f"{sign}{v:,.0f}원"
    except (TypeError, ValueError):
        return "-"


def _profit_color(value) -> discord.Color:
    try:
        v = float(value)
        if v > 0:
            return discord.Color.green()
        elif v < 0:
            return discord.Color.red()
    except (TypeError, ValueError):
        pass
    return discord.Color.greyple()


def _status_color(status: str) -> discord.Color:
    s = str(status).lower()
    if "연동" in s or "모니터링" in s:
        return discord.Color.blue()
    if "정지" in s or "paused" in s:
        return discord.Color.orange()
    if "오류" in s or "error" in s:
        return discord.Color.red()
    return discord.Color.blurple()


# ─────────────────────────────────────────────
# 리포트 생성기
# ─────────────────────────────────────────────
class ReportGenerator:
    """각 action별 Embed 리포트를 생성하는 클래스. 상속으로 확장 가능."""

    def __init__(self, symbol: str, ticker_data: dict):
        self.symbol = symbol
        self.data = ticker_data
        self.now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── 상태 리포트
    def status(self) -> discord.Embed:
        status   = self.data.get("status", "알 수 없음")
        price    = self.data.get("price", 0)
        paused   = self.data.get("paused", False)
        rule     = self.data.get("buy_rule", "-")
        sim      = self.data.get("simulating", False)

        color  = _status_color(status)
        state_icon = "⏸️" if paused else ("▶️" if sim else "🔄")

        embed = discord.Embed(
            title=f"📊 상태 보고서 — {self.symbol}",
            color=color,
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="상태",     value=f"{state_icon} {status}",         inline=True)
        embed.add_field(name="현재가",   value=_fmt_price(price),                 inline=True)
        embed.add_field(name="전략",     value=rule or "-",                        inline=True)
        embed.add_field(name="일시정지", value="✅ 정지 중" if paused else "▶️ 운용 중", inline=True)
        embed.add_field(name="시뮬레이션", value="🔁 실행 중" if sim else "중지",    inline=True)
        embed.set_footer(text=f"조회 시각: {self.now}")
        return embed

    # ── 수익 리포트
    def pnl(self) -> discord.Embed:
        realized = self.data.get("realized_profit", 0)
        price    = self.data.get("price", 0)
        qty      = self.data.get("position_qty", 0)
        avg      = self.data.get("avg_price", 0)

        # 미실현 손익 계산
        unrealized = (float(price) - float(avg)) * int(qty) if qty and avg else 0

        color = _profit_color(realized)
        embed = discord.Embed(
            title=f"💰 수익 보고서 — {self.symbol}",
            color=color,
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="실현 손익",   value=_fmt_profit(realized),   inline=True)
        embed.add_field(name="미실현 손익", value=_fmt_profit(unrealized),  inline=True)
        embed.add_field(name="\u200b",      value="\u200b",                 inline=True)

        if qty:
            embed.add_field(name="보유수량", value=f"{qty}주",              inline=True)
            embed.add_field(name="평균단가", value=_fmt_price(avg),          inline=True)
            embed.add_field(name="현재가",   value=_fmt_price(price),        inline=True)

        embed.set_footer(text=f"조회 시각: {self.now}")
        return embed

    # ── 상세정보 리포트
    def detail(self) -> discord.Embed:
        status   = self.data.get("status", "-")
        price    = self.data.get("price", 0)
        rule     = self.data.get("buy_rule", "-")
        qty      = self.data.get("position_qty", 0)
        avg      = self.data.get("avg_price", 0)
        realized = self.data.get("realized_profit", 0)
        paused   = self.data.get("paused", False)

        embed = discord.Embed(
            title=f"🔍 상세정보 — {self.symbol}",
            color=discord.Color.dark_blue(),
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="현재가",    value=_fmt_price(price),                        inline=True)
        embed.add_field(name="상태",      value=status,                                   inline=True)
        embed.add_field(name="운용 여부", value="⏸️ 정지" if paused else "▶️ 운용",        inline=True)
        embed.add_field(name="전략",      value=rule,                                     inline=True)
        embed.add_field(name="보유수량",  value=f"{qty}주" if qty else "-",               inline=True)
        embed.add_field(name="평균단가",  value=_fmt_price(avg) if avg else "-",           inline=True)
        embed.add_field(name="실현 손익", value=_fmt_profit(realized),                    inline=False)

        # 포지션 정보 요약
        if qty and avg:
            unrealized = (float(price) - float(avg)) * int(qty)
            embed.add_field(
                name="미실현 손익",
                value=f"{_fmt_profit(unrealized)} ({'+' if unrealized >= 0 else ''}{unrealized / (float(avg)*int(qty))*100:.2f}%)",
                inline=False,
            )

        embed.set_footer(text=f"조회 시각: {self.now}")
        return embed

    # ── 알 수 없는 action
    def unknown(self) -> discord.Embed:
        return discord.Embed(
            title="❓ 알 수 없는 요청",
            description=f"`{self.symbol}` 에 대한 해당 요청을 처리할 수 없습니다.",
            color=discord.Color.red(),
        )


# ─────────────────────────────────────────────
# 공개 인터페이스
# ─────────────────────────────────────────────
def generate_report(symbol: str, action: str, ticker_data: dict) -> discord.Embed:
    """
    Parameters
    ----------
    symbol      : 종목명 (예: "SK하이닉스")
    action      : "status" | "pnl" | "detail"
    ticker_data : 백엔드 /status API의 tickers[code] 딕셔너리

    Returns
    -------
    discord.Embed
    """
    generator = ReportGenerator(symbol, ticker_data)
    handler = {
        "status": generator.status,
        "pnl":    generator.pnl,
        "detail": generator.detail,
    }.get(action)

    return handler() if handler else generator.unknown()

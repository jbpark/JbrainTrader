"""
discord_bot/bot.py
==================
Strategy Engine에 통합되어 실행되는 Discord Bot.
engine_instance를 직접 참조하므로 HTTP 호출 없이 데이터를 가져옵니다.

backend/main.py 에서 start_discord_bot(engine_instance) 를 호출하여 시작.
"""

import discord
from discord import app_commands
from discord.ext import tasks
import asyncio
import os
import logging
import threading
from dotenv import load_dotenv

# ─────────────────────────────────────────────
# 리포트 생성기 (같은 폴더의 report.py)
# ─────────────────────────────────────────────
from discord_bot.report import generate_report

# .env 파일을 bot.py 위치 기준 절대경로로 로드
_BOT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(_BOT_DIR, ".env"))

BOT_TOKEN          = os.getenv("DISCORD_BOT_TOKEN", "")
GUILD_ID           = int(os.getenv("DISCORD_GUILD_ID", "0") or "0")
LOG_CHANNEL_ID     = int(os.getenv("DISCORD_LOG_CHANNEL_ID", "0") or "0")
COMMAND_CHANNEL_ID = int(os.getenv("DISCORD_CMD_CHANNEL_ID", "0") or "0")

log = logging.getLogger(__name__)
log.info(f"[Discord] .env 로드됨: GUILD_ID={GUILD_ID}, CMD_CH={COMMAND_CHANNEL_ID}, LOG_CH={LOG_CHANNEL_ID}")

# 전역 봇 인스턴스 (engine에서 로그 전송 시 사용)
_bot_instance = None


# ─────────────────────────────────────────────
# UI 컴포넌트
# ─────────────────────────────────────────────
class SubMenuSelect(discord.ui.Select):
    """두 번째 서브메뉴: 상태 / 수익 / 상세정보"""

    OPTIONS = [
        discord.SelectOption(label="📊 상태",     value="status", description="현재 상태 조회"),
        discord.SelectOption(label="💰 수익",     value="pnl",    description="실현 손익 조회"),
        discord.SelectOption(label="🔍 상세정보", value="detail", description="보유수량, 평균단가 등"),
    ]

    def __init__(self, symbol: str, ticker_data: dict):
        self.symbol      = symbol
        self.ticker_data = ticker_data
        super().__init__(
            placeholder="조회할 항목을 선택하세요...",
            min_values=1, max_values=1,
            options=self.OPTIONS,
        )

    async def callback(self, interaction: discord.Interaction):
        embed = generate_report(self.symbol, self.values[0], self.ticker_data)
        await interaction.response.edit_message(embed=embed, view=self.view)


class TickerSelect(discord.ui.Select):
    """첫 번째 메뉴: 보유 종목 선택"""

    def __init__(self, tickers: dict):
        self.tickers_data = tickers
        options = [
            discord.SelectOption(
                label=info.get("name", code),
                value=code,
                description=f"현재가: {info.get('price', 0):,.0f}원 | {info.get('status', '')}",
                emoji="📈",
            )
            for code, info in list(tickers.items())[:25]
        ] or [discord.SelectOption(label="등록된 종목 없음", value="none", emoji="❌")]

        super().__init__(
            placeholder="종목을 선택하세요...",
            min_values=1, max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        code = self.values[0]
        if code == "none":
            await interaction.response.send_message("등록된 종목이 없습니다.", ephemeral=True)
            return

        ticker_data = self.tickers_data.get(code, {})
        name        = ticker_data.get("name", code)

        view = PortfolioView.__new__(PortfolioView)
        discord.ui.View.__init__(view, timeout=300)
        view.add_item(SubMenuSelect(symbol=name, ticker_data=ticker_data))

        embed = discord.Embed(
            title=f"📌 {name} ({code.split('.')[0]})",
            description="조회할 항목을 아래 메뉴에서 선택하세요.",
            color=discord.Color.blue(),
        )
        embed.set_footer(text="상태 / 수익 / 상세정보 중 선택")
        await interaction.response.edit_message(embed=embed, view=view)


class PortfolioView(discord.ui.View):
    def __init__(self, tickers: dict):
        super().__init__(timeout=300)
        self.add_item(TickerSelect(tickers))

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


# ─────────────────────────────────────────────
# Bot 클라이언트
# ─────────────────────────────────────────────
class TradingBot(discord.Client):

    def __init__(self, engine):
        # 인텐트 설정 (슬래시 커맨드에는 default만으로 충분)
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree           = app_commands.CommandTree(self)
        self.engine         = engine          # StrategyEngine 직접 참조
        self._last_log_len  = 0
        self._bot_loop      = None            # 이 봇의 asyncio 루프

    # ── 슬래시 커맨드 등록
    async def setup_hook(self):
        self._bot_loop = asyncio.get_running_loop()
        
        # 서버 전용 동기화 (즉시 반영)
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            try:
                # 10초 타임아웃으로 엔진 시작 지연 방지
                synced = await asyncio.wait_for(self.tree.sync(guild=guild), timeout=10.0)
                log.info(f"[Discord] 슬래시 커맨드 {len(synced)}개 동기화 완료 (GUILD_ID={GUILD_ID})")
            except Exception as e:
                log.warning(f"[Discord] 커맨드 동기화 실패 (권한 또는 타임아웃): {e}")
        else:
            log.warning("[Discord] GUILD_ID가 설정되지 않아 글로벌 동기화 모드로 동작합니다.")
            await self.tree.sync()
            
        self.log_watch.start()

    async def on_ready(self):
        log.info(f"[Discord] 봇 시작됨: {self.user}")
        log.info(f"[Discord] 등록된 서버: {[g.name for g in self.guilds]}")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching, name="주식 시장 📈"
            )
        )

        # 서비스 시작 메시지 전송
        if LOG_CHANNEL_ID:
            channel = self.get_channel(LOG_CHANNEL_ID)
            if channel:
                try:
                    embed = discord.Embed(
                        title="🚀 서비스 시작",
                        description="트레이딩 엔진 서비스가 재시작되었습니다.",
                        color=discord.Color.green(),
                    )
                    embed.set_footer(text="System Engine Online")
                    await channel.send(embed=embed)
                    log.info(f"[Discord] 로그 채널({LOG_CHANNEL_ID})로 시작 메시지 전송 완료")
                except Exception as e:
                    log.error(f"[Discord] 시작 메시지 전송 실패: {e}")

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """슬래시 커맨드 오류 시 사용자에게 에러 메시지 전송"""
        log.error(f"[Discord] 커맨드 오류 ({interaction.command}): {error}", exc_info=True)
        msg = f"⚠️ 명령 처리 중 오류가 발생했습니다.\n```{str(error)[:200]}```"
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception as e:
            log.error(f"[Discord] 오류 메시지 전송 실패: {e}")

    # ── 로그 채널 전송 (10초마다)
    @tasks.loop(seconds=10)
    async def log_watch(self):
        if not LOG_CHANNEL_ID or not self.engine:
            return
        channel = self.get_channel(LOG_CHANNEL_ID)
        if not channel:
            return

        logs     = self.engine.logs          # engine_instance.logs 직접 접근
        new_logs = logs[self._last_log_len:]
        if new_logs:
            for msg in new_logs[-5:]:
                embed = discord.Embed(
                    description=f"```{msg[:1000]}```",
                    color=discord.Color.dark_gray(),
                )
                await channel.send(embed=embed)
            self._last_log_len = len(logs)

    @log_watch.before_loop
    async def before_log_watch(self):
        await self.wait_until_ready()
        # 봇 시작 시 기존 로그는 건너뜀
        self._last_log_len = len(self.engine.logs) if self.engine else 0

    # ── 외부에서 로그 1건 즉시 전송 (engine.add_log 호출 시 사용 가능)
    def send_log_now(self, message: str):
        if not self._bot_loop or not LOG_CHANNEL_ID:
            return
        channel = self.get_channel(LOG_CHANNEL_ID)
        if not channel:
            return
        embed = discord.Embed(
            description=f"```{message[:1000]}```",
            color=discord.Color.dark_gray(),
        )
        asyncio.run_coroutine_threadsafe(channel.send(embed=embed), self._bot_loop)


# ─────────────────────────────────────────────
# 슬래시 커맨드 등록 함수
# ─────────────────────────────────────────────
def _register_commands(bot: TradingBot):
    """bot 인스턴스를 받아서 슬래시 커맨드를 등록합니다."""

    @bot.tree.command(name="ping", description="봇의 응답 상태를 확인합니다.")
    async def ping(interaction: discord.Interaction):
        await interaction.response.send_message("🏓 Pong! 봇이 정상적으로 작동 중입니다.", ephemeral=True)

    @bot.tree.command(name="help", description="사용 가능한 명령어 목록을 확인합니다.")
    async def help(interaction: discord.Interaction):
        embed = discord.Embed(
            title="📖 트레이딩 봇 명령어 안내",
            description="사용 가능한 슬래시 명령어 목록입니다.",
            color=discord.Color.blue()
        )
        embed.add_field(name="/stock", value="현재 보유 종목 현황 및 상세 정보(상태, 수익, 상세)를 조회합니다.", inline=False)
        embed.add_field(name="/ping", value="봇의 작동 여부를 테스트합니다.", inline=False)
        embed.add_field(name="/help", value="현재 이 도움말 메시지를 출력합니다.", inline=False)
        embed.set_footer(text="Trade Bot Assistant")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="stock", description="현재 보유 종목 현황 및 상세 정보 조회")
    async def stock(interaction: discord.Interaction):
        # 채널 제한 (0이면 모든 채널 허용)
        if COMMAND_CHANNEL_ID and interaction.channel_id != COMMAND_CHANNEL_ID:
            await interaction.response.send_message(
                f"⚠️ 이 명령어는 <#{COMMAND_CHANNEL_ID}> 채널에서만 사용 가능합니다.",
                ephemeral=True,
            )
            return

        try:
            await interaction.response.defer(ephemeral=True, thinking=True)

            # engine_instance.data_store["tickers"] 직접 접근 (HTTP 불필요)
            tickers = {}
            if bot.engine:
                try:
                    tickers = dict(bot.engine.data_store.get("tickers", {}))
                except Exception as e:
                    log.warning(f"[Discord] tickers 접근 실패: {e}")

            embed = discord.Embed(
                title="📊 종목 현황 조회",
                description=(
                    f"**{len(tickers)}개 종목**이 등록되어 있습니다.\n"
                    "상세 정보를 확인하려는 종목을 아래 메뉴에서 선택해주세요."
                ),
                color=discord.Color.green(),
            )
            if tickers:
                embed.add_field(
                    name="등록 종목",
                    value="\n".join(
                        f"• **{v.get('name', k)}** ({k.split('.')[0]})"
                        for k, v in list(tickers.items())[:10]
                    ),
                    inline=False,
                )
            embed.set_footer(text="메뉴 유효시간: 5분")

            view = PortfolioView(tickers)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            log.error(f"[Discord] /portfolio 오류: {e}", exc_info=True)
            msg = f"❌ 오류 발생: `{str(e)[:200]}`"
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(msg, ephemeral=True)
                else:
                    await interaction.response.send_message(msg, ephemeral=True)
            except Exception:
                pass


# ─────────────────────────────────────────────
# 외부 진입점 (backend/main.py 에서 호출)
# ─────────────────────────────────────────────
def start_discord_bot(engine) -> None:
    """
    별도 스레드에서 Discord Bot의 asyncio 루프를 실행합니다.
    backend/main.py 의 __main__ 블록에서 호출하세요.

    Parameters
    ----------
    engine : StrategyEngine 인스턴스
    """
    global _bot_instance

    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        log.warning("[Discord] BOT_TOKEN이 설정되지 않아 Discord Bot을 시작하지 않습니다.")
        return

    bot = TradingBot(engine)
    _register_commands(bot)
    _bot_instance = bot

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(bot.start(BOT_TOKEN))
        except Exception as e:
            log.error(f"[Discord] Bot 실행 오류: {e}")
        finally:
            loop.close()

    t = threading.Thread(target=_run, daemon=True, name="DiscordBotThread")
    t.start()
    log.info("[Discord] Bot 스레드 시작됨")


def get_bot() -> TradingBot | None:
    """현재 실행 중인 봇 인스턴스를 반환합니다."""
    return _bot_instance

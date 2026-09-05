import discord
from discord import app_commands
import os
import asyncio
from dotenv import load_dotenv
import logging

# 상세 로깅 설정
logging.basicConfig(level=logging.INFO)
load_dotenv(dotenv_path=".env")

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", "0") or "0")

class MyClient(discord.Client):
    def __init__(self):
        # 인텐트 최소화
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        if not GUILD_ID:
            print("❌ GUILD_ID가 로드되지 않았습니다. .env를 확인하세요.")
            return

        guild = discord.Object(id=GUILD_ID)

        @self.tree.command(name="ping", description="연결 확인용 핑", guild=guild)
        async def ping(interaction: discord.Interaction):
            print(f"📩 [{interaction.user}] 로부터 /ping 수신")
            await interaction.response.send_message("✅ Pong! 봇이 메시지를 받았습니다.", ephemeral=True)

        print(f"🔄 서버({GUILD_ID})에 명령어 동기화 중...")
        try:
            synced = await self.tree.sync(guild=guild)
            print(f"✅ 동기화 완료: {len(synced)}개 명령어")
        except Exception as e:
            print(f"❌ 동기화 실패: {e}")

    async def on_ready(self):
        print(f"🚀 봇 로그인 성공: {self.user}")
        print(f"연결된 서버: {[g.name for g in self.guilds]}")
        print("이제 디스코드에서 /ping 을 입력해 보세요.")

    async def on_interaction(self, interaction: discord.Interaction):
        print(f"🔔 상호작용 감지내용 (Type: {interaction.type})")

if __name__ == "__main__":
    if not TOKEN:
        print("❌ TOKEN이 없습니다.")
    else:
        client = MyClient()
        client.run(TOKEN)

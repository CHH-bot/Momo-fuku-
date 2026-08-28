import asyncio
import os
import discord
from discord.ext import commands

# 1. 設定機器人權限 (Intents)
intents = discord.Intents.default()
intents.message_content = True

# 2. 初始化 Bot
bot = commands.Bot(command_prefix="!", intents=intents)

# 3. 載入 cogs/ 資料夾內的所有 Cog
async def load_extensions():
    cogs_dir = "./cogs"
    if os.path.exists(cogs_dir):
        for filename in os.listdir(cogs_dir):
            if filename.endswith(".py"):
                cog_name = f"cogs.{filename[:-3]}"
                try:
                    await bot.load_extension(cog_name)
                    print(f"✅ 成功載入 Cog: {cog_name}", flush=True)
                except Exception as e:
                    print(f"❌ 載入 Cog 失敗 [{cog_name}]: {e}", flush=True)

# 4. 當機器人登入成功時觸發
@bot.event
async def on_ready():
    print(f"🤖 機器人已成功連線上線！帳號：{bot.user.name} (ID: {bot.user.id})", flush=True)

    try:
        # 同步全域斜線指令到 Discord
        synced = await bot.tree.sync()
        print(f"✨ 成功同步 {len(synced)} 個斜線指令！", flush=True)
    except Exception as e:
        print(f"❌ 指令同步失敗: {e}", flush=True)

# 5. 主程式進入點
async def main():
    async with bot:
        await load_extensions()
        
        # 讀取你的環境變數 BOT_TOKEN
        token = os.getenv("BOT_TOKEN")
        
        if not token:
            print("⚠️ 錯誤：找不到『BOT_TOKEN』環境變數，請檢查 Render 的 Environment 設定！", flush=True)
            return

        print("🚀 正在使用 BOT_TOKEN 登入 Discord...", flush=True)
        await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())

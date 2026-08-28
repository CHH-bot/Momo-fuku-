import asyncio
import os
import discord
from discord.ext import commands

# 1. 設定機器人權限 (Intents)
intents = discord.Intents.default()
intents.message_content = True  # 啟用訊息內容讀取權限

# 2. 初始化 Bot
bot = commands.Bot(command_prefix="!", intents=intents)


# 3. 定義非同步載入 Cogs 函式
async def load_extensions():
    # 遍歷 cogs 資料夾
    cogs_dir = "./cogs"
    if os.path.exists(cogs_dir):
        for filename in os.listdir(cogs_dir):
            if filename.endswith(".py"):
                # 將檔名轉為 Cog 模組路徑（例：cogs.turtle_escape）
                cog_name = f"cogs.{filename[:-3]}"
                try:
                    await bot.load_extension(cog_name)
                    print(f"✅ 成功載入 Cog: {cog_name}")
                except Exception as e:
                    print(f"❌ 載入 Cog 失敗 [{cog_name}]: {e}")


# 4. 當機器人準備完成（Ready）時同步指令
@bot.event
async def on_ready():
    print(f"🤖 機器人已上線：{bot.user.name} (ID: {bot.user.id})")

    try:
        # 同步所有 app_commands (斜線指令) 到 Discord
        synced = await bot.tree.sync()
        print(f"✨ 成功同步 {len(synced)} 個中文斜線指令！")
    except Exception as e:
        print(f"❌ 同步斜线指令失敗: {e}")


# 5. 主程式入口點
async def main():
    async with bot:
        # 載入所有 Cog
        await load_extensions()
        # 啟動 Bot (請確保已設定環境變數 BOT_TOKEN)
        token = os.getenv("BOT_TOKEN")
        if not token:
            print(
                "⚠️ 找不到 BOT_TOKEN 環境變數，請在環境變數或 .env 中設定！"
            )
            return
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())

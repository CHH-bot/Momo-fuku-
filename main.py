import asyncio
import os
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
  print(f"🎮 遊戲機器人已成功上線！登入身份：{bot.user}")
  try:
    synced = await bot.tree.sync()
    print(f"✅ 已成功同步 {len(synced)} 個斜線指令！")
  except Exception as e:
    print(f"❌ 同步失敗: {e}")


async def load_extensions():
  for filename in os.listdir("./cogs"):
    if filename.endswith(".py"):
      await bot.load_extension(f"cogs.{filename[:-3]}")


async def main():
  async with bot:
    await load_extensions()
    await bot.start(os.getenv("BOT_TOKEN"))


if __name__ == "__main__":
  asyncio.run(main())

import random
import discord
from discord import app_commands
from discord.ext import commands


class GuessTheNumber(commands.Cog):

  def __init__(self, bot):
    self.bot = bot
    self.games = {}

  @app_commands.command(
      name="數字炸彈", description="💣 發起一局數字炸彈（終極密碼）遊戲"
  )
  @app_commands.describe(最大值="請輸入遊戲上限的最大值（最小值固定為 1）")
  async def start_gtn(
      self,
      interaction: discord.Interaction,
      最大值: int,
  ):
    最小值 = 1
    if 最小值 >= 最大值:
      await interaction.response.send_message(
          "❌ **錯誤**：最大值必須大於 1！", ephemeral=True
      )
      return

    ans = random.randint(最小值 + 1, 最大值 - 1)
    self.games[interaction.channel_id] = {
        "ans": ans,
        "min": 最小值,
        "max": 最大值,
    }

    await interaction.response.send_message(
        f"💣 **數字炸彈遊戲已發起！**\n"
        f"📊 **當前數字範圍**：`{最小值}` ~ `{最大值}`\n"
        f"💬 大家直接在頻道輸入數字開始猜測吧！"
    )

  @commands.Cog.listener()
  async def on_message(self, message):
    if message.author.bot or message.channel.id not in self.games:
      return

    if not message.content.isdigit():
      return

    guess = int(message.content)
    game = self.games[message.channel.id]

    if guess <= game["min"] or guess >= game["max"]:
      return

    if guess == game["ans"]:
      await message.channel.send(
          f"💥 **💥 💥 🈲 💣 爆炸了！**\n"
          f"恭喜 {message.author.mention} 踩中炸彈數字 **{guess}**！遊戲結束！"
      )
      del self.games[message.channel.id]
    elif guess < game["ans"]:
      game["min"] = guess
      await message.channel.send(
          f"太小囉！新範圍：`{game['min']}` ~ `{game['max']}`"
      )
    else:
      game["max"] = guess
      await message.channel.send(
          f"太大囉！新範圍：`{game['min']}` ~ `{game['max']}`"
      )


async def setup(bot):
  await bot.add_cog(GuessTheNumber(bot))

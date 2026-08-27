import asyncio
import random
import discord
from discord import app_commands
from discord.ext import commands


class GuessTheNumber(commands.Cog):

  def __init__(self, bot):
    self.bot = bot
    # 紀錄結構: {channel_id: {"ans": int, "min": int, "max": int, "last_player": Member, "allow_consecutive": bool}}
    self.games = {}

  # ------------------------------------------------------------------
  # 指令一：發起數字炸彈
  # ------------------------------------------------------------------
  @app_commands.command(
      name="數字炸彈", description="嘿嘿💣炸彈已埋入！"
  )
  @app_commands.describe(最大值="請輸入上限數字（最小值固定為 1）")
  async def start_gtn(self, interaction: discord.Interaction, 最大值: int):
    channel_id = interaction.channel_id

    # 防呆 1：檢查頻道是否已有遊戲
    if channel_id in self.games:
      embed_error = discord.Embed(
          title="⚠️ 遊戲進行中",
          description="這個頻道已經有一局數字炸彈正在進行囉！\n請先完成當前遊戲或使用 `/拆除炸彈`。",
          color=discord.Color.gold(),
      )
      await interaction.response.send_message(embed_error, ephemeral=True)
      return

    最小值 = 1
    # 防呆 2：數字範圍檢查
    if 最大值 <= 2:
      embed_limit = discord.Embed(
          title="❌ 設定錯誤",
          description="最大值必須大於 2！（否則沒有可猜的數字空間）",
          color=discord.Color.red(),
      )
      await interaction.response.send_message(embed_limit, ephemeral=True)
      return

    ans = random.randint(最小值 + 1, 最大值 - 1)

    self.games[channel_id] = {
        "ans": ans,
        "min": 最小值,
        "max": 最大值,
        "last_player": None,
        "allow_consecutive": False,
    }

    # ✨ 精美 Embed：開局卡片 (金色)
    embed = discord.Embed(
        title="💣 炸彈已埋入！",
        description="看看誰是幸運兒嘻嘻",
        color=0xF1C40F,  # 精美金黃色
    )
    embed.add_field(
        name="初始數字範圍", value=f"`{最小值}` ~ `{最大值}`", inline=True
    )
    embed.add_field(
        name="🚫 連傳限制", value="`禁止一人連續輸入`", inline=True
    )
    embed.add_field(
        name="💬 遊戲玩法",
        value="直接在頻道中**輸入數字**即可參與猜測。",
        inline=False,
    )
    embed.set_footer(
        text="💡 提示：管理者可使用 /設定連傳 更改連續輸入規則"
    )

    await interaction.response.send_message(embed=embed)

  # ------------------------------------------------------------------
  # 指令二：拆除炸彈（手動結束遊戲）
  # ------------------------------------------------------------------
  @app_commands.command(
      name="拆除炸彈", description="✂️ 拆除炸彈"
  )
  async def stop_gtn(self, interaction: discord.Interaction):
    channel_id = interaction.channel_id

    if channel_id not in self.games:
      embed_none = discord.Embed(
          title="❓ 無進行中的遊戲",
          description="當前頻道並沒有正在進行的數字炸彈遊戲。",
          color=discord.Color.dark_gray(),
      )
      await interaction.response.send_message(embed_none, ephemeral=True)
      return

    del self.games[channel_id]

    # ✨ 精美 Embed：拆除成功卡片 (綠色)
    embed = discord.Embed(
        title="✂️ 炸彈成功拆除！",
        description=f"由 {interaction.user.mention} 成功手動拆除炸彈。",
        color=0x2ECC71,  # 翡翠綠
    )
    await interaction.response.send_message(embed=embed)

  # ------------------------------------------------------------------
  # 指令三：管理者設定連續輸入模式
  # ------------------------------------------------------------------
  @app_commands.command(
      name="設定連傳", description="⚙️ (僅限管理者) 設定是否允許同一人連續輸入數字"
  )
  @app_commands.describe(允許連續輸入="True 表示允許一人連續輸入；False 表示禁止")
  @app_commands.checks.has_permissions(manage_messages=True)
  async def set_consecutive(
      self, interaction: discord.Interaction, 允許連續輸入: bool
  ):
    channel_id = interaction.channel_id

    if channel_id not in self.games:
      await interaction.response.send_message(
          "❓ 當前頻道並沒有正在進行的數字炸彈遊戲，請先發起遊戲。",
          ephemeral=True,
      )
      return

    self.games[channel_id]["allow_consecutive"] = 允許連續輸入

    status_str = (
        "✅ **允許**（同一人可連續猜測）"
        if 允許連續輸入
        else "🚫 **禁止**（必須兩人以上交替猜測）"
    )

    # ✨ 精美 Embed：設定變更卡片 (藍紫色)
    embed = discord.Embed(
        title="規則設定已變更",
        description=f"當前連傳狀態：{status_str}",
        color=0x9B59B6,
    )
    await interaction.response.send_message(embed=embed)

  @set_consecutive.error
  async def set_consecutive_error(
      self, interaction: discord.Interaction, error
  ):
    if isinstance(error, app_commands.MissingPermissions):
      await interaction.response.send_message(
          "❌ **權限不足**：只有擁有「管理訊息」權限的管理者才能使用此指令！",
          ephemeral=True,
      )

  # ------------------------------------------------------------------
  # 監聽器：玩家輸入數字處理與 Embedding 卡片回應
  # ------------------------------------------------------------------
  @commands.Cog.listener()
  async def on_message(self, message: discord.Message):
    if message.author.bot or message.channel.id not in self.games:
      return

    if not message.content.isdigit():
      return

    channel_id = message.channel.id
    game = self.games[channel_id]
    guess = int(message.content)

    if guess <= game["min"] or guess >= game["max"]:
      return

    # 判斷連傳規則
    if not game["allow_consecutive"] and game["last_player"] == message.author:
      embed_warning = discord.Embed(
          description=f"⚠️ {message.author.mention} **不能連續輸入** ",
          color=0xE74C3C,
      )
      msg = await message.channel.send(embed=embed_warning)
      await asyncio.sleep(4)
      await msg.delete()  # 自動刪除警告
      return

    game["last_player"] = message.author

    # 狀況 A：踩中炸彈 (劇烈紅色 Embed)
    if guess == game["ans"]:
      embed = discord.Embed(
          title=" 劇 烈 爆 炸 ！！",
          description=f"咻嘣！{message.author.mention} 觸碰了炸彈 **`{guess}`**！",
          color=0xE74C3C,  # 鮮豔紅
      )
      embed.add_field(
          name="幸運炸彈客", value=message.author.mention, inline=True
      )
      # 自動帶入踩中者的 Discord 頭像
      embed.set_thumbnail(url=message.author.display_avatar.url)
      embed.set_footer(text="遊戲結束！使用 /數字炸彈 即可開啟新一局。")

      await message.channel.send(embed=embed)
      del self.games[channel_id]

    # 狀況 B：數字太小 (湛藍色 Embed)
    elif guess < game["ans"]:
      game["min"] = guess
      embed = discord.Embed(
          title="數字太小囉！放膽猜",
          description=f"最新數字範圍縮小為：**`{game['min']}` ~ `{game['max']}`**",
          color=0x3498DB,  # 湛藍色
      )
      embed.set_author(
          name=f"{message.author.display_name} 猜了 {guess}",
          icon_url=message.author.display_avatar.url,
      )
      await message.channel.send(embed=embed)

    # 狀況 C：數字太大 (暖橘色 Embed)
    else:
      game["max"] = guess
      embed = discord.Embed(
          title="數字太大囉！慢慢猜",
          description=f"最新數字範圍縮小為：**`{game['min']}` ~ `{game['max']}`**",
          color=0xE67E22,  # 暖橘色
      )
      embed.set_author(
          name=f"{message.author.display_name} 猜了 {guess}",
          icon_url=message.author.display_avatar.url,
      )
      await message.channel.send(embed=embed)


async def setup(bot):
  await bot.add_cog(GuessTheNumber(bot))

import os
import json
import discord
from discord import app_commands
from discord.ext import commands

class TurtleEscape(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.stories = {}
        self.load_all_stories()

    def load_all_stories(self):
        """動態載入 data/turtle_escape/ 底下的所有 JSON 故事檔"""
        data_dir = "./data/turtle_escape"
        if os.path.exists(data_dir):
            for filename in os.listdir(data_dir):
                if filename.endswith(".json"):
                    filepath = os.path.join(data_dir, filename)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            story_data = json.load(f)
                            story_id = story_data.get("story_id", filename[:-5])
                            self.stories[story_id] = story_data
                            print(f"📖 成功載入密室故事: {story_data.get('title', story_id)}")
                    except Exception as e:
                        print(f"❌ 讀取故事檔案失敗 [{filename}]: {e}")

    # ----------------------------------------------------
    # 中文斜線指令定義
    # ----------------------------------------------------

    @app_commands.command(name="建立隊伍", description="建立密室海龜湯專屬討論串與隊伍")
    async def create_team(self, interaction: discord.Interaction):
        await interaction.response.send_message("🔍 正在為你準備密室逃脫專屬討論串...", ephemeral=True)

    @app_commands.command(name="查看", description="查看當前密室場景與搜集到的線索")
    async def view_scene(self, interaction: discord.Interaction):
        await interaction.response.send_message("📌 當前搜尋到的線索與物件：\n- 床頭櫃的手機\n- 牆角的保險盒", ephemeral=True)

    @app_commands.command(name="提問", description="向海龜湯主持人（Gemini AI）進行判定提問")
    @app_commands.describe(問題="請輸入你想確認的細節（例如：雨衣是小明的嗎？）")
    async def ask_question(self, interaction: discord.Interaction, 問題: str):
        await interaction.response.defer() # 預先等待，防止 API 回應超時
        # 此處放置 Gemini API 判定邏輯
        await interaction.followup.send(f"❓ 你的提問：`{問題}`\n🤖 主持人判定：**【是】**")

    @app_commands.command(name="解鎖", description="輸入 4 位數密碼嘗試打開保險盒解鎖關卡")
    @app_commands.describe(密碼="輸入解密密碼（例如：0412）")
    async def unlock_safe(self, interaction: discord.Interaction, 密碼: str):
        if 密碼 == "0412":
            await interaction.response.send_message("🎉 **解鎖成功！** 你打開了保險盒並發現了真相！")
        else:
            await interaction.response.send_message("❌ **密碼錯誤！** 保險盒發出了嗶嗶警報聲...", ephemeral=True)

# ----------------------------------------------------
# 關鍵：discord.py 載入 Cog 的 Entry Point 入口點
# ----------------------------------------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(TurtleEscape(bot))
    @app_commands.command(name="建立隊伍", description="開啟專屬私密討論串開始密室海龜湯")
    async def create_team(self, interaction: discord.Interaction, 故事編號: str):
        story = self.stories.get(故事編號)
        if not story:
            await interaction.response.send_message("❌ 找不到指定的故事！請確認故事 ID。", ephemeral=True)
            return

        # 1. 建立私密討論串 (Private Thread)
        thread = await interaction.channel.create_thread(
            name=f"🔒【{story['title']}】-{interaction.user.display_name}的隊伍",
            type=discord.ChannelType.private_thread,
            auto_archive_duration=1440
        )

        # 2. 將創建者拉入討論串
        await thread.add_user(interaction.user)

        # 3. 初始化隊伍遊戲狀態
        self.team_states[thread.id] = {
            "story_id": story["story_id"],
            "daily_ask_count": 0,
            "unlocked": False
        }

        # 4. 回覆開覆狀態 (僅本人可見)
        await interaction.response.send_message(
            f"✅成功建立密室討論串！請前往 {thread.mention} 開始遊戲！", 
            ephemeral=True
        )

        # 5. 在討論串發送開場白與海龜湯湯面
        intro_text = (
            f"**【故事：{story['title']}】**\n\n"
            f"**背景簡介：**\n{story.get('introduction', '無')}\n\n"
            f"**海龜湯湯面：**\n> {story.get('turtle_soup', {}).get('surface', '請探索現場...')}\n\n"
            f"**遊戲指令指南：**\n"
            f"• `/查看` ：搜尋密室房間內的區域與道具線索\n"
            f"• `/提問 [問題]` ：向 AI 湯主提問 (每日限制 {story.get('rules', {}).get('daily_ask_limit', 3)} 次)\n"
            f"• `/解鎖 [密碼]` ：輸入密碼驗證解鎖通關\n\n"
            f"*隊友可直接在此討論串內打字討論，一般聊天不會扣除提問額度！*"
        )
        await thread.send(intro_text)

    # 動態選單：自動帶出可選擇的故事 ID
    @create_team.autocomplete("故事編號")
    async def story_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=s["title"], value=s["story_id"])
            for s in self.stories.values()
            if current.lower() in s["title"].lower() or current.lower() in s["story_id"].lower()
        ]

    # ================= 2. 斜線指令：/查看 =================
    @app_commands.command(name="查看", description="檢視密室內可搜尋的區域與道具線索")
    async def inspect_scene(self, interaction: discord.Interaction):
        state = self.team_states.get(interaction.channel_id)
        if not state:
            await interaction.response.send_message("請在專屬的海龜湯私密討論串內使用此指令！", ephemeral=True)
            return

        story = self.stories.get(state["story_id"])
        scenes = story.get("scenes", {})

        # 構建下拉選單選單
        options = []
        for scene_key, scene_info in scenes.items():
            options.append(discord.SelectOption(
                label=scene_info.get("name", scene_key),
                description=scene_info.get("description", "")[:50],
                value=scene_key
            ))

        select = discord.ui.Select(placeholder="選擇你要搜尋的密室區域...", options=options)

        async def select_callback(select_interaction: discord.Interaction):
            chosen_key = select.values[0]
            chosen_scene = scenes[chosen_key]
            
            detail = f"**【搜尋區域：{chosen_scene.get('name')}】**\n{chosen_scene.get('description')}\n\n**搜尋到的線索/物件：**\n"
            items = chosen_scene.get("items", {})
            for item_key, item_desc in items.items():
                detail += f"• **{item_key}**：{item_desc}\n"
            
            await select_interaction.response.edit_message(content=detail, view=None)

        select.callback = select_callback
        view = discord.ui.View()
        view.add_item(select)

        await interaction.response.send_message("**你想搜查密室的哪個區域？**", view=view)

    # ================= 3. 斜線指令：/提問 (對接 Gemini AI) =================
    @app_commands.command(name="提問", description="向 AI 湯主提問 (回答：是/不是/無關)")
    async def ask_question(self, interaction: discord.Interaction, 問題: str):
        state = self.team_states.get(interaction.channel_id)
        if not state:
            await interaction.response.send_message("請在專屬的海龜湯私密討論串內使用此指令！", ephemeral=True)
            return

        story = self.stories.get(state["story_id"])
        max_asks = story.get("rules", {}).get("daily_ask_limit", 3)

        # 檢查提問上限
        if state["daily_ask_count"] >= max_asks:
            await interaction.response.send_message(
                f"**今日提問額度已用盡 ({max_asks}/{max_asks})！**\n"
                f"請整理已有線索與隊友討論，或使用 `/解鎖 [密碼]` 嘗試驗證解鎖。", 
                ephemeral=True
            )
            return

        await interaction.response.defer() # 延遲回應等待 Gemini 運算

        try:
            # 設定 Gemini API Prompt
            system_prompt = story.get("turtle_soup", {}).get(
                "system_prompt",
                "你現在是海龜湯主持人。只能回答『是』、『不是』或『與真相無關』。"
            )
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = f"{system_prompt}\n\n玩家提出的問題：『{問題}』"
            
            response = model.generate_content(prompt)
            ai_answer = response.text.strip()

            # 扣除額度
            state["daily_ask_count"] += 1
            remains = max_asks - state["daily_ask_count"]

            await interaction.followup.send(
                f"**玩家提問：** {問題}\n"
                f"**AI 湯主回應：** {ai_answer}\n"
                f"*(今日剩餘提問額度：{remains}/{max_asks})*"
            )
        except Exception as e:
            print(f"Gemini API 錯誤: {e}")
            await interaction.followup.send("創世神連線繁忙中，請稍後再試。")

    # ================= 4. 斜線指令：/解鎖 =================
    @app_commands.command(name="解鎖", description="輸入密碼解鎖通關")
    async def unlock(self, interaction: discord.Interaction, 密碼: str):
        state = self.team_states.get(interaction.channel_id)
        if not state:
            await interaction.response.send_message("請在專屬的海龜湯私密討論串內使用此指令！", ephemeral=True)
            return

        story = self.stories.get(state["story_id"])
        correct_code = str(story.get("rules", {}).get("unlock_code") or story.get("turtle_soup", {}).get("password"))

        if 密碼.strip() == correct_code:
            state["unlocked"] = True
            truth_summary = story.get("truth", {}).get("summary") or story.get("turtle_soup", {}).get("truth")
            
            await interaction.response.send_message(
                f"**【解鎖成功！】** 密碼正確 ({密碼})！\n\n"
                f"**【海龜湯完整真相揭密】**\n{truth_summary}\n\n"
                f"恭喜你們隊伍成功逃脫！"
            )
        else:
            await interaction.response.send_message(f"❌ **密碼錯誤！** ({密碼}) 無法開啟鎖頭，請繼續搜尋線索！", ephemeral=True)

# Cog 載入函式
async def setup(bot: commands.Bot):
    await bot.add_cog(TurtleEscapeCog(bot))


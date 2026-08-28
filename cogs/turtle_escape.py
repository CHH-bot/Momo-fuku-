import os
import json
import discord
import google.generativeai as genai
from discord import app_commands
from discord.ext import commands

# 1. 初始化 Gemini API
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

SAVE_FILE = "./data/turtle_escape_teams.json"

class TurtleEscape(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.stories = {}
        self.team_states = {}
        self.load_all_stories()
        self.load_team_states() # 開機時自動載入進度

    def load_all_stories(self):
        """動態載入 data/turtle_escape/ 底下的故事 JSON"""
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
                    except Exception as e:
                        print(f"❌ 讀取故事檔案失敗 [{filename}]: {e}", flush=True)

    def save_team_states(self):
        """將隊伍狀態存檔至本地 JSON"""
        try:
            os.makedirs(os.path.dirname(SAVE_FILE), exist_ok=True)
            with open(SAVE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.team_states, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ 存檔隊伍狀態失敗: {e}", flush=True)

    def load_team_states(self):
        """從本地 JSON 載入隊伍狀態（防重啟失效）"""
        if os.path.exists(SAVE_FILE):
            try:
                with open(SAVE_FILE, "r", encoding="utf-8") as f:
                    # JSON 的 key 是字串，轉回 int 作為頻道 ID
                    data = json.load(f)
                    self.team_states = {int(k): v for k, v in data.items()}
                print(f"💾 成功載入 {len(self.team_states)} 個進行中的隊伍紀錄！", flush=True)
            except Exception as e:
                print(f"❌ 載入隊伍紀錄失敗: {e}", flush=True)

    # ================= 1. 斜線指令：/建立隊伍 =================
    @app_commands.command(name="建立隊伍", description="開啟專屬私密討論串開始密室海龜湯")
    @app_commands.describe(故事編號="選擇欲挑戰的故事名稱/ID")
    async def create_team(self, interaction: discord.Interaction, 故事編號: str):
        story = self.stories.get(故事編號)
        if not story:
            await interaction.response.send_message("❌ 找不到指定的故事！請確認故事 ID。", ephemeral=True)
            return

        thread = await interaction.channel.create_thread(
            name=f"🔒【{story['title']}】- {interaction.user.display_name}的隊伍",
            type=discord.ChannelType.private_thread,
            auto_archive_duration=1440
        )
        await thread.add_user(interaction.user)

        # 初始化紀錄並存檔
        self.team_states[thread.id] = {
            "story_id": story["story_id"],
            "daily_ask_count": 0,
            "unlocked": False
        }
        self.save_team_states()

        await interaction.response.send_message(
            f"✅ 成功建立密室討論串！請前往 {thread.mention} 開始遊戲！", 
            ephemeral=True
        )

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

    @create_team.autocomplete("故事編號")
    async def story_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=s.get("title", s["story_id"]), value=s["story_id"])
            for s in self.stories.values()
            if current.lower() in s.get("title", "").lower() or current.lower() in s["story_id"].lower()
        ]

    # ================= 2. 斜線指令：/查看 =================
    @app_commands.command(name="查看", description="檢視密室內可搜尋的區域與道具線索")
    async def inspect_scene(self, interaction: discord.Interaction):
        state = self.team_states.get(interaction.channel_id)
        if not state:
            await interaction.response.send_message("❌ 請在專屬的海龜湯私密討論串內使用此指令！", ephemeral=True)
            return

        story = self.stories.get(state["story_id"])
        scenes = story.get("scenes", {})

        if not scenes:
            await interaction.response.send_message("📌 當前環境沒有可搜尋的區域。", ephemeral=True)
            return

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
    @app_commands.describe(問題="請輸入你想確認的細節（例如：雨衣是小明的嗎？）")
    async def ask_question(self, interaction: discord.Interaction, 問題: str):
        state = self.team_states.get(interaction.channel_id)
        if not state:
            await interaction.response.send_message("❌ 請在專屬的海龜湯私密討論串內使用此指令！", ephemeral=True)
            return

        story = self.stories.get(state["story_id"])
        max_asks = story.get("rules", {}).get("daily_ask_limit", 3)

        if state["daily_ask_count"] >= max_asks:
            await interaction.response.send_message(
                f"⚠️ **今日提問額度已用盡 ({max_asks}/{max_asks})！**\n"
                f"請整理已有線索與隊友討論，或使用 `/解鎖 [密碼]` 嘗試驗證解鎖。", 
                ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                await interaction.followup.send("⚠️ 尚未偵測到 `GEMINI_API_KEY`，請檢查 Render 後台環境變數。")
                return

            genai.configure(api_key=api_key)
            system_prompt = story.get("turtle_soup", {}).get(
                "system_prompt",
                "你現在是海龜湯主持人。只能回答『是』、『不是』或『與真相無關』。"
            )

            # 使用 gemini-pro 避免 1.5 版本 endpoint 404 錯誤
            model = genai.GenerativeModel("gemini-pro")
            prompt = f"{system_prompt}\n\n玩家提出的問題：『{問題}』"
            
            response = model.generate_content(prompt)
            ai_answer = response.text.strip()

            # 更新額度並存檔
            state["daily_ask_count"] += 1
            if hasattr(self, 'save_team_states'):
                self.save_team_states()

            remains = max_asks - state["daily_ask_count"]

            await interaction.followup.send(
                f"**玩家提問：** {問題}\n"
                f"🤖 **AI 湯主回應：** {ai_answer}\n"
                f"*(今日剩餘提問額度：{remains}/{max_asks})*"
            )
        except Exception as e:
            print(f"Gemini API 錯誤: {e}", flush=True)
            await interaction.followup.send(f"⚠️ 連線至 Gemini 時發生錯誤：`{e}`")

    # ================= 4. 斜線指令：/解鎖 =================
    @app_commands.command(name="解鎖", description="輸入密碼解鎖通關")
    @app_commands.describe(密碼="輸入驗證密碼")
    async def unlock(self, interaction: discord.Interaction, 密碼: str):
        state = self.team_states.get(interaction.channel_id)
        if not state:
            await interaction.response.send_message("❌ 請在專屬的海龜湯私密討論串內使用此指令！", ephemeral=True)
            return

        story = self.stories.get(state["story_id"])
        correct_code = str(story.get("rules", {}).get("unlock_code") or story.get("turtle_soup", {}).get("password"))

        if 密碼.strip() == correct_code:
            state["unlocked"] = True
            self.save_team_states()
            truth_summary = story.get("truth", {}).get("summary") or story.get("turtle_soup", {}).get("truth", "恭喜通關！")
            
            await interaction.response.send_message(
                f"🎉 **【解鎖成功！】** 密碼正確 ({密碼})！\n\n"
                f"📖 **【海龜湯完整真相揭密】**\n{truth_summary}\n\n"
                f"恭喜你們隊伍成功逃脫！"
            )
        else:
            await interaction.response.send_message(f"❌ **密碼錯誤！** ({密碼}) 無法開啟鎖頭，請繼續搜尋線索！", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(TurtleEscape(bot))

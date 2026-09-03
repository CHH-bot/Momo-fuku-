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
        self.stories.clear()
        
        if os.path.exists(data_dir):
            for filename in os.listdir(data_dir):
                if filename.endswith(".json"):
                    filepath = os.path.join(data_dir, filename)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            story_data = json.load(f)
                            
                            # 支援直接讀取或相容巢狀外層包覆
                            if len(story_data) == 1 and not any(k in story_data for k in ["story_id", "title", "rules"]):
                                outer_key = list(story_data.keys())[0]
                                story_data = story_data[outer_key]
                            
                            story_id = story_data.get("story_id") or filename[:-5]
                            self.stories[story_id] = story_data
                                
                            print(f"✅ 成功載入故事 [{story_id}] 標題: {story_data.get('title', '無標題')} (檔名: {filename})", flush=True)
                    except Exception as e:
                        print(f"❌ 讀取故事檔案失敗 [{filename}]: {e}", flush=True)
        else:
            print(f"⚠️ 找不到資料夾: {data_dir}", flush=True)

    def save_team_states(self):
        """將隊伍狀態存檔至本地 JSON"""
        try:
            os.makedirs(os.path.dirname(SAVE_FILE), exist_ok=True)
            with open(SAVE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.team_states, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ 存檔隊伍狀態失敗: {e}", flush=True)

    def load_team_states(self):
        """從本地 JSON 載入隊伍狀態"""
        if os.path.exists(SAVE_FILE):
            try:
                with open(SAVE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.team_states = {int(k): v for k, v in data.items()}
                print(f"💾 成功載入 {len(self.team_states)} 個進行中的隊伍紀錄！", flush=True)
            except Exception as e:
                print(f"❌ 載入隊伍紀錄失敗: {e}", flush=True)

    def get_working_gemini_model(self):
        preferred_models = [
            "gemini-3.6-flash", 
            "gemini-3.5-flash", 
            "gemini-2.5-flash", 
            "gemini-1.5-flash-latest",
            "gemini-1.5-flash"
        ]
        try:
            available_models = [
                m.name.replace("models/", "") 
                for m in genai.list_models() 
                if "generateContent" in m.supported_generation_methods
            ]
            for target in preferred_models:
                if target in available_models:
                    return target
            flash_models = [m for m in available_models if "flash" in m]
            return flash_models[0] if flash_models else available_models[0]
        except Exception as err:
            print(f"無法獲取模型列表，使用預設值: {err}", flush=True)
            return "gemini-3.6-flash"

    # ================= 1. 斜線指令：/建立隊伍 =================
    @app_commands.command(name="建立隊伍", description="開啟專屬私密討論串開始密室海龜湯")
    @app_commands.describe(故事編號="選擇欲挑戰的故事名稱/ID")
    async def create_team(self, interaction: discord.Interaction, 故事編號: str):
        # 移除了 ephemeral=True，讓「您已經開啟挑戰」的訊息公開顯示（不自動刪除）
        await interaction.response.defer()

        try:
            story = self.stories.get(故事編號)
            if not story:
                await interaction.followup.send(f"❌ 找不到故事『{故事編號}』！請確認故事 ID 或重新整理。")
                return

            story_title = story.get("title", 故事編號)

            thread = await interaction.channel.create_thread(
                name=f"🔒【{story_title}】- {interaction.user.display_name}的隊伍",
                type=discord.ChannelType.private_thread,
                auto_archive_duration=1440
            )
            await thread.add_user(interaction.user)

            real_story_id = story.get("story_id", 故事編號)
            self.team_states[thread.id] = {
                "story_id": real_story_id,
                "daily_ask_count": 0,
                "unlocked": False
            }
            self.save_team_states()

            # 建立包含 Embed 與圖片的組隊成功訊息
            embed = discord.Embed(
                title=f"🔒 【{story_title}】隊伍建立成功",
                description=f"您已經開啟挑戰\n\n👉 請前往 {thread.mention} 開始遊戲！",
                color=discord.Color.blue()
            )
            
                # 支援從 JSON 讀取圖片連結
    image_url = story.get("image_url")
    if image_url:
        embed.set_image(url=image_url)

            await interaction.followup.send(embed=embed)

            daily_limit = story.get("rules", {}).get("daily_ask_limit", 3)
            turtle_surface = story.get("turtle_soup", {}).get("surface", "請透過 `/查看` 探索現場...")

            intro_text = (
                f"**【故事：{story_title}】**\n\n"
                f"**背景簡介：**\n{story.get('introduction', '無')}\n\n"
                f"**海龜湯湯面：**\n> {turtle_surface}\n\n"
                f"**遊戲指令指南：**\n"
                f"• `/查看` ：搜尋密室房間內的區域與道具線索\n"
                f"• `/提問 [問題]` ：向 **阿努比斯** 提問（上限 {daily_limit} 次）\n"
                f"• `/分析推理 [分析]` ：提交推理，讓 **阿努比斯** 評估還原度\n"
                f"• `/解鎖 [密碼]` ：輸入密碼驗證解鎖通關"
            )
            await thread.send(intro_text)
        except Exception as e:
            print(f"❌ 建立隊伍失敗: {e}", flush=True)
            await interaction.followup.send(f"⚠️ 建立隊伍時發生錯誤：`{e}`")

    # 確保自動完成選單只顯示中文標題
    @create_team.autocomplete("故事編號")
    async def story_autocomplete(self, interaction: discord.Interaction, current: str):
        choices = []
        seen_ids = set()

        for sid, story in self.stories.items():
            real_id = story.get("story_id", sid)
            title = story.get("title", real_id)
            
            if real_id in seen_ids:
                continue
            seen_ids.add(real_id)

            display_name = title

            if (current.lower() in display_name.lower() or 
                current.lower() in real_id.lower()):
                choices.append(app_commands.Choice(name=display_name, value=real_id))

        return choices[:25]

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
            
            detail = f"**【搜尋區域：{chosen_scene.get('name', chosen_key)}】**\n{chosen_scene.get('description', '')}\n\n**搜尋到的線索/物件：**\n"
            items = chosen_scene.get("items", {})
            for item_key, item_desc in items.items():
                detail += f"• **{item_key}**：{item_desc}\n"
            
            await select_interaction.response.edit_message(content=detail, view=None)

        select.callback = select_callback
        view = discord.ui.View()
        view.add_item(select)

        await interaction.response.send_message("**你想搜查密室的哪個區域？**", view=view)

    # ================= 3. 斜線指令：/提問 =================
    @app_commands.command(name="提問", description="向阿努比斯提問 (回答：是/不是/與真相無關)")
    @app_commands.describe(問題="請輸入你想確認的細節")
    async def ask_question(self, interaction: discord.Interaction, 問題: str):
        state = self.team_states.get(interaction.channel_id)
        if not state:
            await interaction.response.send_message("❌ 請在專屬的海龜湯私密討論串內使用此指令！", ephemeral=True)
            return

        story = self.stories.get(state["story_id"])
        max_asks = story.get("rules", {}).get("daily_ask_limit", 3)

        if state["daily_ask_count"] >= max_asks:
            await interaction.response.send_message(
                f"⚠️ **今日提問額度已用盡 ({max_asks}/{max_asks})！**", 
                ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            truth_summary = story.get("truth", {}).get("summary", "")
            system_prompt = (
                f"你現在是海龜湯遊戲的審判者『阿努比斯』。\n"
                f"完整真相：【{truth_summary}】\n"
                f"規則：請根據真相嚴格回答玩家提出的問題。你只能回答『是』、『不是』或『與真相無關』。"
            )

            prompt = f"{system_prompt}\n\n玩家提出的問題：『{問題}』"
            model = genai.GenerativeModel(self.get_working_gemini_model())
            response = model.generate_content(prompt)

            ai_answer = response.text.strip() if response and response.text else "與真相無關"

            state["daily_ask_count"] += 1
            self.save_team_states()
            remains = max_asks - state["daily_ask_count"]

            await interaction.followup.send(
                f"**玩家提問：** {問題}\n"
                f"𓄿 **阿努比斯回應：** {ai_answer}\n"
                f"*(今日剩餘提問額度：{remains}/{max_asks})*"
            )
        except Exception as e:
            await interaction.followup.send(f"⚠️ 連線至 Gemini 時發生錯誤：`{e}`")

    # ================= 4. 斜線指令：/分析推理 =================
    @app_commands.command(name="分析推理", description="讓阿努比斯評估你們對海龜湯真相的推理還原度")
    @app_commands.describe(你的推理="請寫下你認為的事情經過與真相")
    async def analyze_truth(self, interaction: discord.Interaction, 你的推理: str):
        state = self.team_states.get(interaction.channel_id)
        if not state:
            await interaction.response.send_message("❌ 請在專屬的海龜湯私密討論串內使用此指令！", ephemeral=True)
            return

        story = self.stories.get(state["story_id"])
        truth_info = story.get("truth", {})
        truth_summary = truth_info.get("summary", "無真相紀錄")
        keywords = truth_info.get("keywords", [])

        await interaction.response.defer()

        try:
            analysis_prompt = f"""
你是一名海龜湯遊戲的掌秤審判者『阿努比斯』。
【故事真實真相】: {truth_summary}
【核心關鍵字】: {', '.join(keywords)}
【玩家提交的推理】: {你的推理}

請依序回覆：
1. **真相還原度**：[0% ~ 100%]
2. **已推出的重點**：[列出猜對部分]
3. **尚未揭開的盲點**：[適度提示]
4. **審判建議**：[1句話引導]
"""
            model = genai.GenerativeModel(self.get_working_gemini_model())
            response = model.generate_content(analysis_prompt)
            ai_analysis = response.text.strip() if response and response.text else "無法解析"

            await interaction.followup.send(
                f"𓄿 **【阿努比斯 - 審判推理報告】**\n"
                f"**玩家分析：**\n> {你的推理}\n\n{ai_analysis}"
            )
        except Exception as e:
            await interaction.followup.send(f"⚠️ 進行推理分析時發生錯誤：`{e}`")

    # ================= 5. 斜線指令：/解鎖 =================
    @app_commands.command(name="解鎖", description="輸入密碼解鎖通關")
    @app_commands.describe(密碼="輸入驗證密碼")
    async def unlock(self, interaction: discord.Interaction, 密碼: str):
        state = self.team_states.get(interaction.channel_id)
        if not state:
            await interaction.response.send_message("❌ 請在專屬的海龜湯私密討論串內使用此指令！", ephemeral=True)
            return

        story = self.stories.get(state["story_id"])
        correct_code = str(story.get("rules", {}).get("unlock_code", "")).strip()

        if 密碼.strip() == correct_code:
            state["unlocked"] = True
            self.save_team_states()
            
            truth_summary = story.get("truth", {}).get("summary", "恭喜通關！")
            embed = discord.Embed(
                title="🎉 【解鎖成功！恭喜通關】",
                description=f"恭喜隊伍順利輸入正確密碼！",
                color=discord.Color.green()
            )
            embed.add_field(name="🔑 正確密碼", value=f"`{correct_code}`", inline=False)
            embed.add_field(name="📜 真相揭曉", value=truth_summary, inline=False)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                f"❌ **密碼錯誤！** (`{密碼}`) 燈號閃爍紅燈，請重新思考！", 
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(TurtleEscape(bot))

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
        """動態載入 data/turtle_escape/ 底下的故事 JSON (支援 story_1_ 等前綴)"""
        data_dir = "./data/turtle_escape"
        self.stories.clear()
        
        if os.path.exists(data_dir):
            for filename in os.listdir(data_dir):
                if filename.endswith(".json"):
                    filepath = os.path.join(data_dir, filename)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            story_data = json.load(f)
                            
                            story_id = story_data.get("story_id") or filename[:-5]
                            self.stories[story_id] = story_data
                            
                            filename_no_ext = filename[:-5]
                            if filename_no_ext != story_id:
                                self.stories[filename_no_ext] = story_data
                                
                            print(f"✅ 成功載入故事 [{story_id}] (檔名: {filename})", flush=True)
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
                    data = json.load(f)
                    self.team_states = {int(k): v for k, v in data.items()}
                print(f"💾 成功載入 {len(self.team_states)} 個進行中的隊伍紀錄！", flush=True)
            except Exception as e:
                print(f"❌ 載入隊伍紀錄失敗: {e}", flush=True)

    def get_working_gemini_model(self):
        """動態抓取目前 API Key 支援的最佳 Gemini 模型"""
        preferred_models = [
            "gemini-3.6-flash", 
            "gemini-3.5-flash", 
            "gemini-2.5-flash", 
            "gemini-1.5-flash-latest"
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
            return preferred_models[0]

    # ================= 1. 斜線指令：/建立隊伍 =================
    @app_commands.command(name="建立隊伍", description="開啟專屬私密討論串開始密室海龜湯")
    @app_commands.describe(故事編號="選擇欲挑戰的故事名稱/ID")
    async def create_team(self, interaction: discord.Interaction, 故事編號: str):
        # 立即延遲回應，防止 3 秒 Timeout 錯誤
        await interaction.response.defer(ephemeral=True)

        try:
            story = self.stories.get(故事編號)
            if not story:
                await interaction.followup.send(f"❌ 找不到故事『{故事編號}』！請確認故事 ID。", ephemeral=True)
                return

            # 使用 .get("title", ...) 安全防護，防止 KeyError: 'title'
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

            await interaction.followup.send(
                f"✅ 成功建立密室討論串！請前往 {thread.mention} 開始遊戲！", 
                ephemeral=True
            )

            daily_limit = story.get("rules", {}).get("daily_ask_limit", 3)
            turtle_surface = story.get("turtle_soup", {}).get("surface", "請透過 `/查看` 探索現場...")

            intro_text = (
                f"**【故事：{story_title}】**\n\n"
                f"**背景簡介：**\n{story.get('introduction', '無')}\n\n"
                f"**海龜湯湯面：**\n> {turtle_surface}\n\n"
                f"**遊戲指令指南：**\n"
                f"• `/查看` ：搜尋密室房間內的區域與道具線索\n"
                f"• `/提問 [問題]` ：向 **阿努比斯** 提問（僅回答：是 / 不是 / 與真相無關，上限 {daily_limit} 次）\n"
                f"• `/分析推理 [分析]` ：提交你們的推理，讓 **阿努比斯** 評估真相還原度並給予提示\n"
                f"• `/解鎖 [密碼]` ：輸入密碼驗證解鎖通關\n\n"
                f"*隊友可直接在此討論串內打字討論，一般聊天不會扣除提問額度！*"
            )
            await thread.send(intro_text)
        except Exception as e:
            print(f"❌ 建立隊伍失敗: {e}", flush=True)
            await interaction.followup.send(f"⚠️ 建立隊伍時發生錯誤：`{e}`", ephemeral=True)

    @create_team.autocomplete("故事編號")
    async def story_autocomplete(self, interaction: discord.Interaction, current: str):
        choices = []
        seen_ids = set()

        for sid, story in self.stories.items():
            real_id = story.get("story_id", sid)
            title = story.get("title", real_id)
            
            # 防止別名導致重複選單
            if real_id in seen_ids:
                continue
            seen_ids.add(real_id)

            # 格式化選單名稱
            display_name = f"【{real_id}】{title}"

            # 關鍵字搜尋過濾
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
                f"⚠️ **今日提問額度已用盡 ({max_asks}/{max_asks})！**\n"
                f"請整理已有線索與隊友討論，使用 `/分析推理` 確認方向，或使用 `/解鎖 [密碼]` 嘗試通關。", 
                ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                await interaction.followup.send("⚠️ 尚未偵測到 `GEMINI_API_KEY`，請檢查環境變數。")
                return

            genai.configure(api_key=api_key)
            
            truth_summary = story.get("truth", {}).get("summary") or story.get("turtle_soup", {}).get("truth", "")
            system_prompt = (
                f"你現在是海龜湯遊戲的審判者『阿努比斯』。\n"
                f"完整真相：【{truth_summary}】\n"
                f"規則：請根據真相嚴格回答玩家提出的問題。你只能回答『是』、『不是』或『與真相無關』這三種答案之一，嚴禁提供額外的解釋或暴雷。"
            )

            prompt = f"{system_prompt}\n\n玩家提出的問題：『{問題}』"
            selected_model_name = self.get_working_gemini_model()

            model = genai.GenerativeModel(selected_model_name)
            response = model.generate_content(prompt)

            if not response or not response.text:
                raise Exception("API 回傳內容為空。")

            ai_answer = response.text.strip()

            state["daily_ask_count"] += 1
            self.save_team_states()

            remains = max_asks - state["daily_ask_count"]

            await interaction.followup.send(
                f"**玩家提問：** {問題}\n"
                f"𓄿 **阿努比斯回應：** {ai_answer}\n"
                f"*(今日剩餘提問額度：{remains}/{max_asks})*"
            )
        except Exception as e:
            print(f"Gemini API 錯誤詳情: {e}", flush=True)
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
        truth_summary = truth_info.get("summary") or story.get("turtle_soup", {}).get("truth", "無真相紀錄")
        keywords = truth_info.get("keywords", [])

        await interaction.response.defer()

        try:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                await interaction.followup.send("⚠️ 尚未偵測到 `GEMINI_API_KEY`，請檢查環境變數。")
                return

            genai.configure(api_key=api_key)

            analysis_prompt = f"""
你是一名海龜湯遊戲的掌秤審判者『阿努比斯』。

【故事真實真相】:
{truth_summary}

【核心關鍵字列表】:
{', '.join(keywords)}

【玩家提交的推理分析】:
{你的推理}

請嚴格按照以下格式回覆玩家：
1. **真相還原度**：[給出 0% ~ 100% 的分數]
2. **已推出的核心重點**：[條列式列出玩家猜對的部分]
3. **尚未揭開的盲點/遺漏**：[條列式給予適度提示，但切勿直接揭曉全部真相]
4. **阿努比斯的審判建議**：[給予 1 句話引導，若還原度高可提醒尋找密碼並使用 `/解鎖`]
"""
            model_name = self.get_working_gemini_model()
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(analysis_prompt)

            ai_analysis = response.text.strip()

            await interaction.followup.send(
                f"𓄿 **【阿努比斯 - 審判推理報告】**\n"
                f"**玩家提出的分析：**\n> {你的推理}\n\n"
                f"{ai_analysis}"
            )
        except Exception as e:
            print(f"Gemini API 分析錯誤: {e}", flush=True)
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
        if not story:
            await interaction.response.send_message("⚠️ 找不到故事資料！", ephemeral=True)
            return

        correct_code = str(
            story.get("rules", {}).get("unlock_code") or 
            story.get("turtle_soup", {}).get("password", "")
        ).strip()

        if 密碼.strip() == correct_code:
            state["unlocked"] = True
            self.save_team_states()
            
            truth_summary = story.get("truth", {}).get("summary") or story.get("turtle_soup", {}).get("truth", "恭喜通關！")
            
            embed = discord.Embed(
                title="🎉 【解鎖成功！恭喜通關】",
                description=f"恭喜隊伍 **{interaction.channel.name}** 順利輸入正確密碼！",
                color=discord.Color.green()
            )
            embed.add_field(name="🔑 正確密碼", value=f"`{correct_code}`", inline=False)
            embed.add_field(name="📜 海龜湯真相揭曉", value=truth_summary, inline=False)
            embed.set_footer(text="感謝遊玩！討論串可繼續留存討論或由管理員關閉。")

            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                f"❌ **密碼錯誤！** (`{密碼}`) 無法開啟鎖頭，請觀察 `/查看` 獲得的線索或用 `/分析推理` 獲取協助！", 
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(TurtleEscape(bot))

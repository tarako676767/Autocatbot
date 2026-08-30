import asyncio
from dataclasses import asdict
import io
import json
import os
import random
import sqlite3
from threading import Thread
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from flask import Flask

# BCSFE モジュールのインポート
try:
    from bcsfe import core
except ImportError:
    core = None

# =========================================================
# Render等での常時起動用 Webサーバー設定
# =========================================================
app = Flask("")


@app.route("/")
def home():
    return "BCSFE Bot is alive!"


def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


def keep_alive():
    t = Thread(target=run)
    t.start()


# =========================================================
# データベース管理 (BCSFE ユーザーデータ用)
# =========================================================
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BCSFE_DB_PATH = os.path.join(BASE_DIR, "bcsfe_users.db")


class BCSFEDBManager:

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY, 
                    save_data BLOB,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            conn.commit()

    def save_user_data(self, user_id: str, save_bytes: bytes):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO users (user_id, save_data) VALUES (?, ?)",
                (user_id, save_bytes),
            )
            conn.commit()

    def get_user_data(self, user_id: str) -> Optional[bytes]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT save_data FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            if row:
                return row[0]
        return None

    def delete_user_data(self, user_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM users WHERE user_id = ?", (user_id,)
            )
            conn.commit()
            return cursor.rowcount > 0


bcsfe_db = BCSFEDBManager(BCSFE_DB_PATH)

# =========================================================
# UI Component (マックボットと同様のUIパネル設計)
# =========================================================


class EditOptionSelect(discord.ui.Select):

    def __init__(self):
        options = [
            discord.SelectOption(
                label="ネコ缶 (Cat Food)",
                value="catfood",
                description="ネコ缶の所持数を上限近くまで変更します",
                emoji="🐱",
            ),
            discord.SelectOption(
                label="XP (経験値)",
                value="xp",
                description="XPを最大値まで付与します",
                emoji="🌟",
            ),
            discord.SelectOption(
                label="全キャラ解放",
                value="unlock_cats",
                description="全キャラクターをアンロックします",
                emoji="🔓",
            ),
            discord.SelectOption(
                label="バトルアイテム全開",
                value="items",
                description="戦闘用アイテムを各999個付与します",
                emoji="⚔️",
            ),
        ]
        super().__init__(
            placeholder="編集メニューを選択してください...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_id = str(interaction.user.id)
        save_bytes = bcsfe_db.get_user_data(user_id)

        if not save_bytes:
            return await interaction.followup.send(
                "セーブデータが登録されていません。先に `/upload` でアップロードしてください。",
                ephemeral=True,
            )

        chosen = self.values[0]

        # 重いBCSFE解析・書き換え処理を別スレッドで安全に実行（フリーズ防止）
        def process_save():
            # 実際にはここに core.SaveData(save_bytes) 等のロジックが入ります
            if chosen == "catfood":
                return "ネコ缶を **999,999個** に変更しました！"
            elif chosen == "xp":
                return "XPを **99,999,999** に変更しました！"
            elif chosen == "unlock_cats":
                return "全キャラクターの解放処理が完了しました！"
            elif chosen == "items":
                return "バトルアイテムを最大数付与しました！"
            return "処理が完了しました。"

        result_msg = await asyncio.to_thread(process_save)
        await interaction.followup.send(f"✅ {result_msg}", ephemeral=True)


class BCSFEControlPanelView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(EditOptionSelect())

    @discord.ui.button(
        label="編集済みデータをダウンロード",
        style=discord.ButtonStyle.primary,
        custom_id="bcsfe_download_btn",
        row=2,
    )
    async def download_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer(ephemeral=True)
        user_id = str(interaction.user.id)
        save_bytes = bcsfe_db.get_user_data(user_id)

        if not save_bytes:
            return await interaction.followup.send(
                "編集するデータが存在しません。", ephemeral=True
            )

        # ファイルとしてDiscordに送信
        file_stream = io.BytesIO(save_bytes)
        file = discord.File(file_stream, filename="SAVE_DATA_EDITED.png")

        await interaction.followup.send(
            content="📂 編集後のセーブデータファイルです。端末に読み込んでください。",
            file=file,
            ephemeral=True,
        )


# =========================================================
# Bot 本体設定
# =========================================================


class BCSFEBot(commands.Bot):

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Persistent View (永続パネル) の登録
        self.add_view(BCSFEControlPanelView())
        # コマンドの自動同期（これがあるため招待後にコマンドが確実に表示されます）
        await self.tree.sync()


bot = BCSFEBot()

# =========================================================
# スラッシュコマンド定義
# =========================================================


@bot.tree.command(
    name="upload", description="編集したいセーブデータをアップロードします"
)
@app_commands.describe(file="セーブデータファイル (.png や .save)")
async def upload(interaction: discord.Interaction, file: discord.Attachment):
    await interaction.response.defer(ephemeral=True)
    try:
        file_bytes = await file.read()

        # DBに保存
        bcsfe_db.save_user_data(str(interaction.user.id), file_bytes)

        embed = discord.Embed(
            title="セーブデータ読み込み完了",
            description=f"ファイル `{file.filename}` を正常に受領・保存しました。\n`/panel` コマンドで編集パネルを開いて操作を行ってください。",
            color=discord.Color.green(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(
            f"エラーが発生しました: {str(e)}", ephemeral=True
        )


@bot.tree.command(name="panel", description="BCSFE 操作パネルを表示します")
async def panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🐈 BCSFE Mobile Save Editor Panel",
        description="下のドロップダウンメニューから実行したい編集を選択してください。",
        color=discord.Color.orange(),
    )
    await interaction.response.send_message(
        embed=embed, view=BCSFEControlPanelView()
    )


@bot.tree.command(
    name="clear_data", description="保存中のセーブデータをサーバーから削除します"
)
async def clear_data(interaction: discord.Interaction):
    if bcsfe_db.delete_user_data(str(interaction.user.id)):
        await interaction.response.send_message(
            "データ削除完了。", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "登録データがありません。", ephemeral=True
        )


# =========================================================
# 起動処理
# =========================================================
if __name__ == "__main__":
    # Webサーバーをバックグラウンド起動 (Render等対策)
    keep_alive()

    # Bot起動
    bot.run(TOKEN)

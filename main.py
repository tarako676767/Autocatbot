import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import discord
from discord.ext import commands

# BCSFEのコア機能をインポート
try:
    from bcsfe import core
    print("BCSFE core successfully imported!")
except Exception as e:
    print(f"Error importing BCSFE core: {e}")

# 1. RenderのWeb Service維持用ダミーサーバー
class DummyServerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def start_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), DummyServerHandler)
    server.serve_forever()

threading.Thread(target=start_web_server, daemon=True).start()


# 2. Discord Bot 本体
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

# 動作確認コマンド
@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

# 例: セーブデータを添付して実行する読み込み確認コマンド
@bot.command()
async def check(ctx):
    # ファイルが添付されているか確認
    if not ctx.message.attachments:
        await ctx.send("⚠️ セーブデータを添付して `!check` と送信してください。")
        return

    attachment = ctx.message.attachments[0]
    file_path = f"./{attachment.filename}"
    
    # 添付ファイルを一時保存
    await attachment.save(file_path)

    try:
        # BCSFE内部処理でセーブデータをロード
        save_data = core.GameData.from_file(file_path)
        await ctx.send(f"✅ セーブデータの読み込み成功！ (ゲームバージョン: {save_data.game_version})")
    except Exception as e:
        await ctx.send(f"❌ 読み込みエラー: {e}")
    finally:
        # 一時ファイルを削除
        if os.path.exists(file_path):
            os.remove(file_path)

# Bot起動
token = os.environ.get("DISCORD_TOKEN")
if token:
    bot.run(token)
else:
    print("ERROR: DISCORD_TOKEN is not set.")

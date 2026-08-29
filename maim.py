import os
import discord
from discord.ext import commands
from bcsfe import core

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Bot logged in as {bot.user.name}')

@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

# 添付されたセーブデータを受け取って復号・暗号化テストをする例
@bot.command()
async def check_save(ctx):
    if not ctx.message.attachments:
        await ctx.send("セーブデータを添付してコマンドを実行してください。")
        return

    attachment = ctx.message.attachments[0]
    file_path = f"./{attachment.filename}"
    await attachment.save(file_path)

    try:
        # BCSFEの内部処理を直接呼び出し（inputを完全に回避）
        save_data = core.GameData.from_file(file_path)
        await ctx.send(f"✅ セーブデータの読み込みに成功しました！（バージョン: {save_data.game_version}）")
    except Exception as e:
        await ctx.send(f"❌ エラーが発生しました: {e}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

# 環境変数からトークンを取得して起動
bot.run(os.environ.get("DISCORD_TOKEN"))

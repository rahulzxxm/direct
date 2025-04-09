import os
import subprocess
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message
import logging
import re

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load .env
load_dotenv()
API_ID = 22609670
API_HASH = "3506d8474ad1f4f5e79b7c52a5c3e88d"
BOT_TOKEN = "7573531892:AAHLInXIBQkZiq9x9fiR2LSO0VyMk_8YbXc"


# Bot client
app = Client("spayee_uploader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- Spayee Download Function ---
def download_spayee(url, hls_key, save_name):
    command = f'N_m3u8dl-re "{url}" --custom-hls-key "{hls_key}" --save-name "{save_name}" --auto-select -M mp4'
    logger.info(f"Running command: {command}")
    try:
        subprocess.run(command, shell=True, check=True)
        return os.path.join(os.getcwd(), f"{save_name}.mp4")
    except subprocess.CalledProcessError as e:
        logger.error(f"Download failed: {e}")
        return None

# --- Bot Command Handlers ---

@app.on_message(filters.command("start"))
async def start_handler(client, message: Message):
    await message.reply(
        "👋 Welcome! Upload your Spayee URL `.txt` file.\n\n"
        "Each line must be like:\n"
        '`--save-name "video name" "video_url" --custom-hls-key "hls_key"`'
    )

@app.on_message(filters.document & filters.private)
async def handle_spayee_file(client, message: Message):
    logger.info(f"User {message.from_user.id} uploaded a file.")
    
    file_path = await client.download_media(message.document, file_name="spayee_urls.txt")
    logger.info(f"Downloaded to: {file_path}")

    with open(file_path, "r") as f:
        lines = f.readlines()

    pattern = r'--save-name\s+"([^"]+)"\s+"([^"]+)"\s+--custom-hls-key\s+"([^"]+)"'

    for line in lines:
        line = line.strip()
        match = re.match(pattern, line)

        if match:
            save_name, url, hls_key = match.groups()
            await message.reply(f"🔄 Downloading: {save_name}")

            video_path = download_spayee(url, hls_key, save_name)
            if video_path:
                await message.reply_video(video_path, caption=f"✅ {save_name} uploaded!")
                os.remove(video_path)
                logger.info(f"Cleaned up: {video_path}")
            else:
                await message.reply(f"❌ Failed: {save_name}")
        else:
            await message.reply("❌ Invalid line format. Please use:\n--save-name \"name\" \"url\" --custom-hls-key \"key\"")

    os.remove(file_path)
    logger.info(f"Deleted uploaded file: {file_path}")

# Run the bot
app.run()

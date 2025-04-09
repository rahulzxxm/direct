import os
import re
import subprocess
import sys
import shutil
import logging
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message

# Setup logging
LOG_FILE = "spayee_log.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Constants
FFMPEG_PATH = shutil.which("ffmpeg") or "ffmpeg"
DOWNLOADER_PATH = "./N_m3u8DL-RE"
SAVE_DIR = "downloads"

# Check downloader tool
def check_dependencies():
    if not os.path.isfile(DOWNLOADER_PATH):
        raise Exception(f"Downloader not found: {DOWNLOADER_PATH}")
    if not os.access(DOWNLOADER_PATH, os.X_OK):
        os.chmod(DOWNLOADER_PATH, 0o755)
    if not shutil.which("ffmpeg"):
        raise Exception("ffmpeg not found in PATH!")

# Download video from spayee
def download_spayee(url, hls_key, save_name):
    command = [
        DOWNLOADER_PATH,
        url,
        "--custom-hls-key", hls_key,
        "--save-name", save_name,
        "--auto-select",
        "-M", "format=mp4",
        "--ffmpeg-binary-path", FFMPEG_PATH
    ]
    try:
        subprocess.run(command, check=True)
        return os.path.join(SAVE_DIR, save_name + ".mp4")
    except subprocess.CalledProcessError as e:
        logger.error(f"Download failed: {e}")
        return None

def sanitize_filename(name):
    return re.sub(r'[^a-zA-Z0-9_-]', '_', name)

# Telegram bot
app = Client("spayee_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message(filters.command("start"))
async def start(_, message: Message):
    await message.reply_text(
        "Send a `.txt` file with each line in this format:\n"
        '`--save-name "Video Name" "video_url" --custom-hls-key "KEY"`'
    )

@app.on_message(filters.document & filters.private)
async def handle_txt(_, message: Message):
    file_path = await message.download()
    await message.reply_text("⏳ Processing your file...")
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            match = re.match(r'--save-name\s+"([^"]+)"\s+"([^"]+)"\s+--custom-hls-key\s+"([^"]+)"', line.strip())
            if match:
                save_name, url, key = match.groups()
                safe_name = sanitize_filename(save_name)
                await message.reply_text(f"🔽 Downloading: {save_name}")
                path = download_spayee(url, key, safe_name)
                if path and os.path.exists(path):
                    await message.reply_video(path, caption=f"✅ {save_name}")
                    os.remove(path)
                else:
                    await message.reply_text(f"❌ Failed: {save_name}")
    os.remove(file_path)

# Run
if __name__ == "__main__":
    check_dependencies()
    app.run()

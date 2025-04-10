import os
import re
import sys
import shutil
import logging
import asyncio
import subprocess
from pathlib import Path
from pyrogram import Client, filters
from pyrogram.types import Message
from dotenv import load_dotenv

# ---------------------- Logging ----------------------
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

# ---------------------- Load Environment ----------------------
load_dotenv()
API_ID = int(os.getenv("API_ID", "22609670"))
API_HASH = os.getenv("API_HASH", "3506d8474ad1f4f5e79b7c52a5c3e88d")
BOT_TOKEN = os.getenv("BOT_TOKEN", "6611654088:AAE_ACVRTLoucGh_YpnJcuqauyRI3c1cHbw")

# ---------------------- Paths ----------------------
FFMPEG_PATH = shutil.which("ffmpeg") or "ffmpeg"
DOWNLOADER_PATH = "./N_m3u8DL-RE"
SAVE_DIR = Path("downloads")
SAVE_DIR.mkdir(exist_ok=True)

# ---------------------- Dependency Check ----------------------
def check_dependencies():
    if not os.path.isfile(DOWNLOADER_PATH):
        raise FileNotFoundError(f"{DOWNLOADER_PATH} not found")
    if not os.access(DOWNLOADER_PATH, os.X_OK):
        os.chmod(DOWNLOADER_PATH, 0o755)
    if not shutil.which("ffmpeg"):
        raise EnvironmentError("ffmpeg not found in PATH")
    logger.info("All dependencies are okay.")

# ---------------------- Filename Sanitization ----------------------
def sanitize_filename(name: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_-]', '_', name)

# ---------------------- Spayee Downloader ----------------------
async def download_spayee(url: str, hls_key: str, save_name: str) -> Path:
    command = [
        DOWNLOADER_PATH,
        url,
        "--custom-hls-key", hls_key,
        "--save-name", save_name,
        "--auto-select",
        "-M", "format=mp4",
        "--ffmpeg-binary-path", FFMPEG_PATH
    ]
    logger.info(f"Running: {' '.join(command)}")
    try:
        await asyncio.to_thread(subprocess.run, command, check=True)
        video_path = SAVE_DIR / f"{save_name}.mp4"
        return video_path if video_path.exists() else None
    except subprocess.CalledProcessError as e:
        logger.error(f"Download failed: {e}")
        return None

# ---------------------- Bot Setup ----------------------
app = Client("spayee_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message(filters.command("start") & filters.private)
async def start_handler(_, message: Message):
    await message.reply_text(
        "👋 Hello! Send me a `.txt` file where each line looks like:\n\n"
        '`--save-name "Video Name" "video_url" --custom-hls-key "KEY"`'
    )

@app.on_message(filters.document & filters.private)
async def file_handler(_, message: Message):
    file_path = await message.download()
    await message.reply_text("📥 Processing file...")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        logger.error(f"File read error: {e}")
        await message.reply_text("❌ Failed to read file.")
        os.remove(file_path)
        return

    for line in lines:
        line = line.strip()
        match = re.match(r'--save-name\s+"([^"]+)"\s+"([^"]+)"\s+--custom-hls-key\s+"([^"]+)"', line)
        if not match:
            await message.reply_text(f"⚠️ Invalid format:\n{line}")
            continue

        save_name, url, key = match.groups()
        safe_name = sanitize_filename(save_name)
        await message.reply_text(f"🔽 Downloading: {save_name}")
        video_path = await download_spayee(url, key, safe_name)

        if video_path:
            await message.reply_video(str(video_path), caption=f"✅ {save_name}")
            try:
                video_path.unlink()
            except Exception as e:
                logger.error(f"Delete error: {e}")
        else:
            await message.reply_text(f"❌ Failed: {save_name}")

    os.remove(file_path)

# ---------------------- Run Bot ----------------------
if __name__ == "__main__":
    try:
        check_dependencies()
    except Exception as e:
        logger.error(f"Dependency Error: {e}")
        sys.exit(1)
    app.run()

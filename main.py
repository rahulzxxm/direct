import os
import re
import subprocess
import sys
import shutil
import logging
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message

# ----------------------------------
# Logging configuration
# ----------------------------------
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

# ----------------------------------
# Load environment variables
# ----------------------------------
load_dotenv()
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ----------------------------------
# Constants and Paths
# ----------------------------------
FFMPEG_PATH = shutil.which("ffmpeg") or "ffmpeg"
DOWNLOADER_PATH = "./N_m3u8DL-RE"
SAVE_DIR = Path("downloads")
SAVE_DIR.mkdir(exist_ok=True)  # Ensure the downloads directory exists

# ----------------------------------
# Check Required Dependencies
# ----------------------------------
def check_dependencies():
    if not os.path.isfile(DOWNLOADER_PATH):
        raise Exception(f"Downloader not found: {DOWNLOADER_PATH}")
    if not os.access(DOWNLOADER_PATH, os.X_OK):
        os.chmod(DOWNLOADER_PATH, 0o755)
    if not shutil.which("ffmpeg"):
        raise Exception("ffmpeg not found in PATH!")
    logger.info("All dependencies are satisfied.")

# ----------------------------------
# Utility: Filename Sanitization
# ----------------------------------
def sanitize_filename(name: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_-]', '_', name)

# ----------------------------------
# Download Spayee Video (Async)
# ----------------------------------
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
    logger.info(f"Running command: {' '.join(command)}")
    try:
        # Run the command asynchronously in a thread to prevent blocking the event loop
        await asyncio.to_thread(subprocess.run, command, check=True)
        video_path = SAVE_DIR / f"{save_name}.mp4"
        if video_path.exists():
            return video_path
        else:
            raise FileNotFoundError(f"Downloaded file not found at {video_path}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Download failed: {e}")
        return None

# ----------------------------------
# Telegram Bot Setup
# ----------------------------------
app = Client("spayee_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message(filters.command("start"))
async def start_handler(_, message: Message):
    await message.reply_text(
        "Hello!\n\n"
        "Send a `.txt` file where each line is in the format:\n"
        '`--save-name "Video Name" "video_url" --custom-hls-key "KEY"`'
    )

@app.on_message(filters.document & filters.private)
async def handle_txt_file(_, message: Message):
    file_path = await message.download()
    await message.reply_text("⏳ Processing your file...")
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        await message.reply_text("❌ Error reading file.")
        os.remove(file_path)
        return

    for line in lines:
        line = line.strip()
        # Expected format: --save-name "Video Name" "video_url" --custom-hls-key "KEY"
        match = re.match(
            r'--save-name\s+"([^"]+)"\s+"([^"]+)"\s+--custom-hls-key\s+"([^"]+)"',
            line
        )
        if match:
            save_name, url, key = match.groups()
            safe_name = sanitize_filename(save_name)
            await message.reply_text(f"🔽 Downloading: {save_name}")
            video_path = await download_spayee(url, key, safe_name)
            if video_path and video_path.exists():
                await message.reply_video(str(video_path), caption=f"✅ {save_name}")
                try:
                    video_path.unlink()  # Delete the file after upload
                except Exception as exc:
                    logger.error(f"Error deleting file {video_path}: {exc}")
            else:
                await message.reply_text(f"❌ Failed to download: {save_name}")
        else:
            logger.warning(f"Skipping invalid line: {line}")
            await message.reply_text(f"❌ Invalid format: {line}")
    os.remove(file_path)  # Cleanup the uploaded .txt file

# ----------------------------------
# Run the Bot
# ----------------------------------
if __name__ == "__main__":
    try:
        check_dependencies()
    except Exception as exc:
        logger.error(f"Dependency check failed: {exc}")
        sys.exit(1)
    app.run()

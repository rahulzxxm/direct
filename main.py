import os
import json
import re
import subprocess
import time
import sys
import shutil
import logging
from pyrogram import Client, filters
from pyrogram.types import Message

# ---------------------
# Logging configuration
# ---------------------
LOG_FILE = "vps_log.log"
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)

# Telegram API credentials
API_ID = "22609670"
API_HASH = "3506d8474ad1f4f5e79b7c52a5c3e88d"
BOT_TOKEN = "8051949636:AAHAMwENBTrDlzWRSAQRvHSteTnJXgHIP3o"

# Linux defaults for VPS deployment
# Initially set ffmpeg path to "ffmpeg"; the check will update to an absolute path if available.
FFMPEG_PATH = "ffmpeg"
DOWNLOADER_PATH = "./N_m3u8DL-RE"
SAVE_DIR = "downloads"

def check_dependencies():
    # Check if the downloader tool exists and is executable.
    if not os.path.isfile(DOWNLOADER_PATH):
        raise Exception(f"Downloader tool not found at {DOWNLOADER_PATH}!")
    if not os.access(DOWNLOADER_PATH, os.X_OK):
        logging.warning(f"{DOWNLOADER_PATH} is not executable. Attempting to chmod +x")
        os.chmod(DOWNLOADER_PATH, 0o755)
        if not os.access(DOWNLOADER_PATH, os.X_OK):
            raise Exception("Downloader tool is still not executable!")
    logging.info(f"{DOWNLOADER_PATH} is present and executable.")

    # Check for ffmpeg using shutil.which.
    global FFMPEG_PATH
    ffmpeg_found = shutil.which(FFMPEG_PATH)
    if not ffmpeg_found:
        ffmpeg_found = shutil.which("ffmpeg")
        if ffmpeg_found:
            FFMPEG_PATH = ffmpeg_found
            logging.info(f"ffmpeg found at {FFMPEG_PATH}")
        else:
            raise Exception("ffmpeg not found in PATH!")
    else:
        FFMPEG_PATH = ffmpeg_found
        logging.info(f"ffmpeg found at {FFMPEG_PATH}")

# Call dependency check before starting the bot
check_dependencies()

# Initialize the bot
bot = Client("video_downloader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def progress(current, total, message, name):
    percent = current * 100 / total
    try:
        message.edit_text(f"Uploading {name}: {percent:.1f}%")
    except Exception as e:
        logging.error("Progress update error: %s", str(e))

def sanitize_filename(filename):
    # Replace any character that is not alphanumeric, underscore, or dash with an underscore.
    return re.sub(r'[^a-zA-Z0-9_-]', '_', filename)

###############################
# JSON file processing
###############################
def download_video_json(entry, temp_dir):
    mpd = entry["mpd"]
    name = sanitize_filename(entry["name"])
    keys = entry.get("keys", [])
    command = [
        DOWNLOADER_PATH,
        mpd,
        "-M", "format=mp4",
        "--save-name", name,
        "--thread-count", "64",
        "--append-url-params",
        "-mt",
        "--auto-select"
    ]
    for key in keys:
        command.extend(["--key", key])
    os.makedirs(temp_dir, exist_ok=True)
    command.extend(["--save-dir", temp_dir])
    logging.debug("Running command (JSON): %s", " ".join(command))
    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        logging.info("N_m3u8DL-RE output: %s", result.stdout)
        return os.path.join(temp_dir, f"{name}.mp4")
    except subprocess.CalledProcessError as e:
        err_msg = f"Download failed with exit code {e.returncode}. Stderr: {e.stderr}"
        logging.error(err_msg)
        raise Exception(err_msg)

def process_json_file(client, message: Message):
    try:
        file_path = message.download()
        message.reply_text("JSON file received. Processing...")
        with open(file_path, "r") as f:
            data = json.load(f)
        temp_dir = SAVE_DIR
        for entry in data:
            name = sanitize_filename(entry["name"])
            message.reply_text(f"Starting download for: {name}")
            try:
                video_path = download_video_json(entry, temp_dir)
                if not os.path.exists(video_path):
                    message.reply_text(f"Download failed for {name}: File not found")
                    continue
                message.reply_text(f"Download complete. Starting upload for: {name}")
                start_time = time.time()
                client.send_video(
                    chat_id=message.chat.id,
                    video=video_path,
                    caption=f"Uploaded: {name}",
                    progress=lambda current, total: progress(current, total, message, name),
                    width=1920,
                    height=1080
                )
                end_time = time.time()
                message.reply_text(f"Upload complete for {name}. Time taken: {end_time - start_time:.2f} seconds")
                if os.path.exists(video_path):
                    os.remove(video_path)
                    logging.info("Deleted file: %s", video_path)
            except Exception as e:
                logging.error("Error processing JSON entry for %s: %s", name, str(e))
                message.reply_text(f"Error processing {name}: {str(e)}")
                continue
        message.reply_text("All videos processed successfully!")
    except Exception as e:
        logging.error("Error in JSON processing: %s", str(e))
        message.reply_text(f"An error occurred: {str(e)}")

###############################
# TXT file processing (file input)
###############################
def process_txt_file(client, message: Message):
    try:
        file_path = message.download()
        message.reply_text("Text file received. Processing...")
        with open(file_path, "r", encoding="utf-8") as f:
            input_text = f.read()
        lines = [line.strip() for line in input_text.strip().splitlines() if line.strip()]
        videos = []
        if len(lines) % 3 == 0:
            # Each entry is three lines: title, URL, key (with optional HLS_KEY= prefix)
            for i in range(0, len(lines), 3):
                title = lines[i]
                url = lines[i + 1]
                key_line = lines[i + 2]
                key = key_line[len("HLS_KEY="):].strip() if key_line.startswith("HLS_KEY=") else key_line
                videos.append((title, url, key))
        else:
            # Fallback using barrier regex
            for line in lines:
                match = re.match(r"\((.*?)\).*?\(video\):(.*?)HLS_KEY=(.+)", line)
                if match:
                    title, url, key = match.groups()
                    videos.append((title.strip(), url.strip(), key.strip()))
        if not videos:
            message.reply_text("No valid video links found in the text file.")
            return
        os.makedirs(SAVE_DIR, exist_ok=True)
        for title, url, key in videos:
            safe_title = sanitize_filename(title)
            message.reply_text(f"Starting download for: {title}")
            temp_dir = os.path.join(SAVE_DIR, safe_title + "_temp")
            os.makedirs(temp_dir, exist_ok=True)
            command = [
                DOWNLOADER_PATH,
                url,
                "--save-dir", temp_dir,
                "--save-name", safe_title,
                "--custom-hls-key", key,
                "-M", "format=mp4",
                "--ffmpeg-binary-path", FFMPEG_PATH,
                "--auto-select",
                "--log-level", "DEBUG"
            ]
            logging.debug("Running command (TXT file): %s", " ".join(command))
            try:
                result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                logging.info("N_m3u8DL-RE output: %s", result.stdout)
            except subprocess.CalledProcessError as e:
                err_msg = f"Download failed with exit code {e.returncode}. Stderr: {e.stderr}"
                logging.error(err_msg)
                message.reply_text(f"Error processing {title}: {err_msg}")
                continue
            audio_file = None
            for file in os.listdir(temp_dir):
                if file.startswith(safe_title) and file.endswith(".m4a"):
                    audio_file = os.path.join(temp_dir, file)
                    break
            video_file = os.path.join(temp_dir, safe_title + ".mp4")
            final_output = os.path.join(SAVE_DIR, safe_title + ".mp4")
            if audio_file:
                merge_command = [
                    FFMPEG_PATH,
                    "-i", video_file,
                    "-i", audio_file,
                    "-c:v", "copy",
                    "-c:a", "copy",
                    final_output
                ]
                logging.debug("Running ffmpeg merge command: %s", " ".join(merge_command))
                try:
                    result = subprocess.run(merge_command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    logging.info("ffmpeg merge output: %s", result.stdout)
                except subprocess.CalledProcessError as e:
                    err_msg = f"Merging failed with exit code {e.returncode}. Stderr: {e.stderr}"
                    logging.error(err_msg)
                    message.reply_text(f"Error processing {title}: {err_msg}")
                    continue
                if os.path.exists(video_file):
                    os.remove(video_file)
                if os.path.exists(audio_file):
                    os.remove(audio_file)
                try:
                    os.rmdir(temp_dir)
                    logging.info("Removed temp directory: %s", temp_dir)
                except OSError:
                    shutil.rmtree(temp_dir)
                    logging.info("Force removed temp directory: %s", temp_dir)
            else:
                final_output = video_file
                message.reply_text(f"Warning: No audio file found for {title}, skipping merge.")
                try:
                    os.rmdir(temp_dir)
                    logging.info("Removed temp directory: %s", temp_dir)
                except OSError:
                    shutil.rmtree(temp_dir)
                    logging.info("Force removed temp directory: %s", temp_dir)
            message.reply_text(f"Download complete. Starting upload for: {title}")
            start_time = time.time()
            client.send_video(
                chat_id=message.chat.id,
                video=final_output,
                caption=f"Uploaded: {title}",
                progress=lambda current, total: progress(current, total, message, title),
                width=1920,
                height=1080
            )
            end_time = time.time()
            message.reply_text(f"Upload complete for {title}. Time taken: {end_time - start_time:.2f} seconds")
            if os.path.exists(final_output):
                os.remove(final_output)
                logging.info("Deleted final video file: %s", final_output)
        message.reply_text("All videos processed successfully!")
    except Exception as e:
        logging.error("Error in TXT file processing: %s", str(e))
        message.reply_text(f"An error occurred while processing text file: {str(e)}")

###############################
# Text message processing (direct input)
###############################
@bot.on_message(filters.private & filters.text)
def process_text_input(client, message: Message):
    text = message.text.strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) != 3:
        message.reply_text("Please send exactly three lines: first line for the name, second for the URL, and third for the key (optionally starting with 'HLS_KEY=').")
        return
    title = lines[0]
    url = lines[1]
    key_line = lines[2]
    key = key_line[len("HLS_KEY="):].strip() if key_line.startswith("HLS_KEY=") else key_line
    safe_title = sanitize_filename(title)
    message.reply_text(f"Starting download for: {title}")
    temp_dir = os.path.join(SAVE_DIR, safe_title + "_temp")
    os.makedirs(temp_dir, exist_ok=True)
    command = [
        DOWNLOADER_PATH,
        url,
        "--save-dir", temp_dir,
        "--save-name", safe_title,
        "--custom-hls-key", key,
        "-M", "format=mp4",
        "--ffmpeg-binary-path", FFMPEG_PATH,
        "--auto-select",
        "--log-level", "DEBUG"
    ]
    logging.debug("Running command (direct text input): %s", " ".join(command))
    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        logging.info("N_m3u8DL-RE output: %s", result.stdout)
    except subprocess.CalledProcessError as e:
        err_msg = f"Download failed with exit code {e.returncode}. Stderr: {e.stderr}"
        logging.error(err_msg)
        message.reply_text(f"Error processing {title}: {err_msg}")
        return
    audio_file = None
    for file in os.listdir(temp_dir):
        if file.startswith(safe_title) and file.endswith(".m4a"):
            audio_file = os.path.join(temp_dir, file)
            break
    video_file = os.path.join(temp_dir, safe_title + ".mp4")
    final_output = os.path.join(SAVE_DIR, safe_title + ".mp4")
    if audio_file:
        merge_command = [
            FFMPEG_PATH,
            "-i", video_file,
            "-i", audio_file,
            "-c:v", "copy",
            "-c:a", "copy",
            final_output
        ]
        logging.debug("Running ffmpeg merge command: %s", " ".join(merge_command))
        try:
            result = subprocess.run(merge_command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            logging.info("ffmpeg merge output: %s", result.stdout)
        except subprocess.CalledProcessError as e:
            err_msg = f"Merging failed with exit code {e.returncode}. Stderr: {e.stderr}"
            logging.error(err_msg)
            message.reply_text(f"Error processing {title}: {err_msg}")
            return
        if os.path.exists(video_file):
            os.remove(video_file)
        if os.path.exists(audio_file):
            os.remove(audio_file)
        try:
            os.rmdir(temp_dir)
            logging.info("Removed temp directory: %s", temp_dir)
        except OSError:
            shutil.rmtree(temp_dir)
            logging.info("Force removed temp directory: %s", temp_dir)
    else:
        final_output = video_file
        message.reply_text(f"Warning: No audio file found for {title}, skipping merge.")
        try:
            os.rmdir(temp_dir)
            logging.info("Removed temp directory: %s", temp_dir)
        except OSError:
            shutil.rmtree(temp_dir)
            logging.info("Force removed temp directory: %s", temp_dir)
    message.reply_text(f"Download complete. Starting upload for: {title}")
    start_time = time.time()
    client.send_video(
        chat_id=message.chat.id,
        video=final_output,
        caption=f"Uploaded: {title}",
        progress=lambda current, total: progress(current, total, message, title),
        width=1920,
        height=1080
    )
    end_time = time.time()
    message.reply_text(f"Upload complete for {title}. Time taken: {end_time - start_time:.2f} seconds")
    if os.path.exists(final_output):
        os.remove(final_output)
        logging.info("Deleted final video file: %s", final_output)

###############################
# Document file handler for documents
###############################
@bot.on_message(filters.private & filters.document)
def handle_file(client, message: Message):
    file_name = message.document.file_name
    if file_name.endswith(".json"):
        process_json_file(client, message)
    elif file_name.endswith(".txt"):
        process_txt_file(client, message)
    else:
        message.reply_text("Please send a valid .json or .txt file.")

###############################
# Bot restart command
###############################
@bot.on_message(filters.private & filters.command("restart"))
def restart_bot(client, message: Message):
    try:
        message.reply_text("Restarting the bot...")
        python_executable = sys.executable
        os.execl(python_executable, python_executable, *sys.argv)
    except Exception as e:
        logging.error("Failed to restart: %s", str(e))
        message.reply_text(f"Failed to restart: {str(e)}")

if __name__ == "__main__":
    bot.run()

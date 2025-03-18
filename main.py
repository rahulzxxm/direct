import os
import json
import re
import subprocess
import time
import sys
from pyrogram import Client, filters
from pyrogram.types import Message

API_ID = "22609670"
API_HASH = "3506d8474ad1f4f5e79b7c52a5c3e88d"
BOT_TOKEN = "7805856791:AAE_9bEkeN_b9nJLwcLrHigf6bhzXvJACKA"

# Initialize the bot
bot = Client("video_downloader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def progress(current, total, message, name):
    percent = current * 100 / total
    message.edit_text(f"Uploading {name}: {percent:.1f}%")

def sanitize_filename(filename):
    return re.sub(r'[<>:"/\\|?*]', '_', filename)

def download_video(entry, temp_dir):
    mpd = entry["mpd"]
    name = sanitize_filename(entry["name"])
    keys = entry["keys"]

    if not os.path.isfile("./N_m3u8DL-RE"):
        raise Exception("N_m3u8DL-RE tool is missing!")

    command = [
        "./N_m3u8DL-RE",
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

    try:
        subprocess.run(command, check=True)
        return os.path.join(temp_dir, f"{name}.mp4")
    except subprocess.CalledProcessError as e:
        raise Exception(f"Download failed: {str(e)}")

@bot.on_message(filters.private & filters.document)
def handle_json_file(client, message: Message):
    try:
        if not message.document.file_name.endswith(".json"):
            message.reply_text("Please send a valid .json file.")
            return

        file_path = message.download()
        message.reply_text("JSON file received. Processing...")

        with open(file_path, "r") as f:
            data = json.load(f)

        temp_dir = "downloads"

        for entry in data:
            name = sanitize_filename(entry["name"])
            message.reply_text(f"Starting download for: {name}")

            try:
                # Download the video
                video_path = download_video(entry, temp_dir)

                if not os.path.exists(video_path):
                    message.reply_text(f"Download failed for {name}: File not found")
                    continue

                message.reply_text(f"Download complete. Starting upload for: {name}")

                # Upload the video
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
                time_taken = end_time - start_time
                message.reply_text(f"Upload complete for {name}. Time taken: {time_taken:.2f} seconds")

                # Clean up
                if os.path.exists(video_path):
                    os.remove(video_path)

            except Exception as e:
                message.reply_text(f"Error processing {name}: {str(e)}")
                continue

        message.reply_text("All videos processed successfully!")

    except Exception as e:
        message.reply_text(f"An error occurred: {str(e)}")

@bot.on_message(filters.private & filters.command("restart"))
def restart_bot(client, message: Message):
    try:
        message.reply_text("Restarting the bot...")
        # Save the current script file path
        python = sys.executable
        os.execl(python, python, *sys.argv)
    except Exception as e:
        message.reply_text(f"Failed to restart: {str(e)}")

if __name__ == "__main__":
    bot.run()

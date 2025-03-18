# Use an appropriate base image
FROM python:3.9

# Set the working directory inside the container
WORKDIR /app

# Copy all files from the current directory to the container
COPY . .

# Install ffmpeg on the VPS (Debian-based)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Ensure the Linux executable has the correct permissions
RUN chmod +x N_m3u8DL-RE

# Install dependencies
RUN pip install -r requirements.txt

# Set the entry point for the application
CMD ["python", "main.py"]

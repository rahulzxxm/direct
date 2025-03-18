# Use the official Python 3.9 image as the base
FROM python:3.9

# Set the working directory in the container
WORKDIR /app

# Copy all files from the current directory (repo) to the container
COPY . .

# Install ffmpeg (and any other dependencies you might need)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Ensure the Linux executable for N_m3u8DL-RE is executable
RUN chmod +x N_m3u8DL-RE

# Install Python dependencies
RUN pip install -r requirements.txt

# Set the entry point for the application
CMD ["python", "main.py"]

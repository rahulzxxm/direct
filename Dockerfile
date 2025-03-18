# Use an appropriate base image
FROM python:3.9

# Set the working directory inside the container
WORKDIR /app

# Copy your project files into the container
COPY . .

# Install required packages (ffmpeg, wget, and tar)
RUN apt-get update && apt-get install -y ffmpeg wget tar && rm -rf /var/lib/apt/lists/*

# Download and extract the Linux binary for N_m3u8DL-RE
RUN wget -O N_m3u8DL-RE_linux-x64.tar.gz "https://github.com/nilaoda/N_m3u8DL-RE/releases/download/N_m3u8DL-RE_v0.3.0-beta/N_m3u8DL-RE_v0.3.0-beta_linux-x64.tar.gz" && \
    tar -xzf N_m3u8DL-RE_linux-x64.tar.gz && \
    chmod +x N_m3u8DL-RE && \
    rm N_m3u8DL-RE_linux-x64.tar.gz

# Install Python dependencies
RUN pip install -r requirements.txt

# Set the entry point for the application
CMD ["python", "main.py"]

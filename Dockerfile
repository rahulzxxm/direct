# Use an appropriate base image
FROM python:3.9

# Set the working directory inside the container
WORKDIR /app

# Copy all files from the current directory to the container
COPY . .

# Ensure the executable has the correct permissions
RUN chmod +x N_m3u8DL-RE.exe

# Install dependencies
RUN pip install -r requirements.txt

# Set the entry point for the application
CMD ["python", "main.py"]

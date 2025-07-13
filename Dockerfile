# Use official Python image
FROM python:3.9-slim

# Set working directory
WORKDIR /usr/src/app

# Install system dependencies (if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the port Tornado runs on (default is 8888)
EXPOSE 8888

# Command to run the application
CMD ["python", "your_tornado_app.py"]
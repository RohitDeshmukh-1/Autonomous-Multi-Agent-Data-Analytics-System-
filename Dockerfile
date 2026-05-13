# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Set work directory
WORKDIR /app

# Install system dependencies (needed for some python packages like WeasyPrint)
RUN apt-get update && apt-get install -if \
    build-essential \
    python3-dev \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Pre-download the embedding model so it's baked into the image
# This saves ~420MB of bandwidth on every deploy and makes starts instant
RUN python scripts/download_model.py

# Expose the port
EXPOSE 8000

# Start the application
CMD uvicorn api.main:app --host 0.0.0.0 --port $PORT

# Slim News Podcast API Dockerfile
# 목표: 3GB → ~1GB

FROM python:3.12-slim

# Install only essential system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy only necessary code
COPY podcastfy/ ./podcastfy/
COPY data/ ./data/

# Create necessary directories
RUN mkdir -p /app/data/audio/tmp /app/data/transcripts /app/data/sources

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "podcastfy.api.news_podcast_api"]

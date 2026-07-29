# Production Dockerfile for SEC EDGAR Natural Language Analyst Cloud Run Service

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt-get/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Expose Cloud Run default port
EXPOSE 8080

# Start Uvicorn FastAPI production web server using shell expansion for $PORT
CMD ["sh", "-c", "uvicorn agent.api:app --host 0.0.0.0 --port ${PORT:-8080}"]

FROM python:3.11-slim

WORKDIR /app

# Install curl for HEALTHCHECK
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install minimal runtime dependencies
COPY requirements-runtime.txt .
RUN pip install --no-cache-dir -r requirements-runtime.txt

# Copy only what is needed: src, config, data/sample, docs/*.json, frontend/dist
COPY src/ ./src/
COPY config/ ./config/
COPY data/sample/ ./data/sample/
COPY docs/*.json ./docs/
COPY frontend/dist/ ./frontend/dist/

# Ensure offline execution and unbuffered logs
ENV PYTHONUNBUFFERED=1 \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "src.engine.serve", "--host", "0.0.0.0", "--port", "8000"]

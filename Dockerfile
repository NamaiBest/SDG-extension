FROM python:3.11-slim

WORKDIR /app

# System deps for sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code + data
COPY raw_data/ raw_data/
COPY app/ app/
COPY outputs/ outputs/

# API key files are mounted at runtime (not baked into image)
# e.g.  -v ./gemini_api_key.txt:/app/gemini_api_key.txt:ro

EXPOSE 8000

# Index the vector store on first boot, then start the server
CMD ["python", "-m", "uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000"]

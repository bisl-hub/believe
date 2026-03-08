# Build the high-throughput Go worker
FROM golang:1.21-bullseye AS go-builder
WORKDIR /go/src/app
COPY src/llm_worker/ ./
RUN go build -o llm_worker -x main.go

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Pipeline Code
COPY src /app/src
COPY --from=go-builder /go/src/app/llm_worker /app/src/llm_worker/llm_worker

# Entrypoint
# We run the module src.main
ENV PYTHONPATH=/app
ENTRYPOINT ["python", "-m", "src.main"]

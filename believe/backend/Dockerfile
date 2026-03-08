FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Docker CLI (for sibling container management)
RUN curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Backend Code
COPY app /app/backend/app

# Create output directory
RUN mkdir -p /app/outputs

# Expose port
EXPOSE 8000

# Run FastAPI
# Note: We are running from /app, so the module path is backend.app.main:app
# But wait, we copied app to /app/backend/app.
# Let's adjust.
# If we are in /app, and we want to import backend.app.main
# We should probably copy app to /app/app and run app.main:app if we were running from /app
# BUT, the imports inside the code use relative imports like `from ..db import ...`
# This implies `app` is a package.
# So we should run `uvicorn app.main:app` from the parent directory of `app`.
# So let's copy `app` to `/app/app`.

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]

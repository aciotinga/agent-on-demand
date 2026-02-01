FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy capsule code
COPY . .

# Set working directory for execution
WORKDIR /app

# Default command (run.py will be called by orchestrator)
CMD ["python", "run.py"]

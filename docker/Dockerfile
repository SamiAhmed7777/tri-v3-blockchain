FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libffi-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create necessary directories
RUN mkdir -p data logs

# Expose ports
EXPOSE 8333 8332

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV NODE_ENV=production

# Run the node
CMD ["python", "-m", "src.main"] 
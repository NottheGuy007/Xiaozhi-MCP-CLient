FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY reminder_server.py .
COPY reminder_notifier.py .
COPY mcp_pipe.py .
COPY web_server.py .
COPY smithery_connector.py .
COPY auto_connect_manager.py .
COPY reminder_with_smithery.py .
COPY servers_config.json .
COPY start.sh .

# Make start script executable
RUN chmod +x start.sh

# Install Node.js and npm for npx support
RUN apt-get update && apt-get install -y nodejs npm && rm -rf /var/lib/apt/lists/*

# Create data directory for SQLite database
RUN mkdir -p /app/data

# Set database path
ENV DB_PATH=/app/data/reminders.db
ENV PYTHONUNBUFFERED=1

# Default command (can be overridden)
CMD ["./start.sh"]

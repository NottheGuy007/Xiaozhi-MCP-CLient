#!/bin/bash

echo "=================================================="
echo "Starting Xiaozhi Reminder Server on Render"
echo "=================================================="

# Create data directory if it doesn't exist
mkdir -p /app/data

# Set database path
export DB_PATH=/app/data/reminders.db

# Choose which server to run (with or without Smithery)
if [ "$ENABLE_SMITHERY" = "true" ]; then
    export MCP_SCRIPT=reminder_with_smithery.py
    echo "Using Smithery-enabled server"
else
    export MCP_SCRIPT=reminder_server.py
    echo "Using standard reminder server"
fi

echo "Database path: $DB_PATH"
echo "MCP Script: $MCP_SCRIPT"

# Initialize database by running the appropriate server once
echo "Initializing database..."
timeout 5 python $MCP_SCRIPT || true

# Check if database was created
if [ -f "$DB_PATH" ]; then
    echo "✓ Database initialized successfully"
    ls -lh "$DB_PATH"
else
    echo "✗ Warning: Database not found, will be created on first use"
fi

echo "=================================================="
echo "Starting MCP Pipe Server..."
echo "=================================================="

# Start MCP server in background
python mcp_pipe.py &
MCP_PID=$!

echo "MCP Server started with PID: $MCP_PID"

# Wait a bit for MCP server to initialize
sleep 3

echo "=================================================="
echo "Starting Reminder Notifier..."
echo "=================================================="

# Start notifier in background
python reminder_notifier.py &
NOTIFIER_PID=$!

echo "Notifier started with PID: $NOTIFIER_PID"

echo "=================================================="
echo "Starting Web Server (keeps Render port open)..."
echo "=================================================="

# Start web server in foreground (this keeps the container running)
python web_server.py

# If web server exits, stop other processes
echo "Web server stopped, shutting down..."
kill $MCP_PID 2>/dev/null || true
kill $NOTIFIER_PID 2>/dev/null || true
wait

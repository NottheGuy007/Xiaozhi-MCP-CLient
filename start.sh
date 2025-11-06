#!/bin/bash

# Start the MCP server in background
python mcp_pipe.py &

# Wait a bit for database initialization
sleep 5

# Start the notifier in foreground
python reminder_notifier.py

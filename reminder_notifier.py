import sqlite3
import logging
import sys
import os
import asyncio
import websockets
import json
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("reminder_notifier")

DB_PATH = Path(os.getenv("DB_PATH", "/app/data/reminders.db"))


async def send_notification_to_xiaozhi(reminder):
    """Send notification to Xiaozhi via WebSocket"""
    token = os.getenv("XIAOZHI_TOKEN")
    if not token:
        logger.error("XIAOZHI_TOKEN not set, cannot send notification")
        return False
    
    uri = f"wss://api.xiaozhi.me/mcp/?token={token}"
    
    try:
        async with websockets.connect(uri, ping_interval=20, ping_timeout=10) as ws:
            notification_message = {
                "jsonrpc": "2.0",
                "method": "notifications/message",
                "params": {
                    "level": "info",
                    "message": f"⏰ REMINDER: {reminder['title']}",
                    "data": {
                        "id": reminder['id'],
                        "title": reminder['title'],
                        "description": reminder['description'],
                        "datetime": reminder['datetime']
                    }
                }
            }
            
            await ws.send(json.dumps(notification_message))
            logger.info(f"Notification sent for reminder: {reminder['id']} - {reminder['title']}")
            return True
            
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        return False


def get_due_reminders():
    """Get reminders that are due now (within the next 1 minute)"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        now = datetime.now()
        one_minute_later = now + timedelta(minutes=1)
        
        cursor.execute("""
            SELECT * FROM reminders
            WHERE completed = 0 
            AND notified = 0
            AND reminder_datetime <= ?
            ORDER BY reminder_datetime ASC
        """, (one_minute_later.isoformat(),))
        
        rows = cursor.fetchall()
        conn.close()
        
        reminders = []
        for row in rows:
            reminders.append({
                "id": row["id"],
                "title": row["title"],
                "description": row["description"],
                "datetime": row["reminder_datetime"],
                "user_id": row["user_id"]
            })
        
        return reminders
        
    except Exception as e:
        logger.error(f"Error getting due reminders: {e}")
        return []


def mark_as_notified(reminder_id):
    """Mark a reminder as notified"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE reminders 
            SET notified = 1
            WHERE id = ?
        """, (reminder_id,))
        
        conn.commit()
        conn.close()
        logger.info(f"Marked reminder {reminder_id} as notified")
        return True
        
    except Exception as e:
        logger.error(f"Error marking reminder as notified: {e}")
        return False


async def check_and_notify():
    """Main function to check and send notifications"""
    logger.info("Checking for due reminders...")
    
    due_reminders = get_due_reminders()
    
    if not due_reminders:
        logger.info("No due reminders found")
        return
    
    logger.info(f"Found {len(due_reminders)} due reminder(s)")
    
    for reminder in due_reminders:
        logger.info(f"Processing reminder: {reminder['id']} - {reminder['title']}")
        
        success = await send_notification_to_xiaozhi(reminder)
        
        if success:
            mark_as_notified(reminder['id'])
            logger.info(f"Successfully notified for reminder: {reminder['id']}")
        else:
            logger.warning(f"Failed to notify for reminder: {reminder['id']}")


async def continuous_monitoring():
    """Continuously monitor for due reminders every minute"""
    logger.info("Starting continuous reminder monitoring...")
    
    while True:
        try:
            await check_and_notify()
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
        
        logger.info("Waiting 60 seconds before next check...")
        await asyncio.sleep(60)


if __name__ == "__main__":
    if not DB_PATH.exists():
        logger.error(f"Database not found at {DB_PATH}")
        logger.error("Please run reminder_server.py first to initialize the database")
        sys.exit(1)
    
    mode = os.getenv("NOTIFIER_MODE", "continuous")
    
    if mode == "once":
        logger.info("Running in single-check mode")
        asyncio.run(check_and_notify())
    else:
        logger.info("Running in continuous monitoring mode")
        asyncio.run(continuous_monitoring())

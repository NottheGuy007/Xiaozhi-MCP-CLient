import sys
import json
import logging
import sqlite3
import os
from datetime import datetime, timedelta
from mcp.server.fastmcp import FastMCP
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("reminder_server")

mcp = FastMCP("Xiaozhi Reminder Server")

DB_PATH = Path(os.getenv("DB_PATH", "/app/data/reminders.db"))


def init_database():
    """Initialize SQLite database with reminders table"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            reminder_datetime TEXT NOT NULL,
            completed INTEGER DEFAULT 0,
            notified INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            completed_at TEXT,
            user_id TEXT DEFAULT 'default'
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_reminder_datetime 
        ON reminders(reminder_datetime)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_completed 
        ON reminders(completed)
    """)
    
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")


def parse_datetime(datetime_str):
    """Parse datetime string with multiple format support"""
    formats = [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%d-%m-%Y %H:%M",
        "%m/%d/%Y %H:%M"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(datetime_str, fmt)
        except ValueError:
            continue
    
    raise ValueError(f"Unable to parse datetime: {datetime_str}. Use format: YYYY-MM-DD HH:MM")


@mcp.tool()
def add_reminder(title: str, datetime_str: str, description: str = "", user_id: str = "default"):
    """Add a new reminder with title, datetime (YYYY-MM-DD HH:MM), and optional description"""
    try:
        reminder_time = parse_datetime(datetime_str)
        
        if reminder_time < datetime.now():
            return json.dumps({
                "success": False,
                "error": "Cannot create reminder for past time"
            }, indent=2)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO reminders (title, description, reminder_datetime, created_at, user_id)
            VALUES (?, ?, ?, ?, ?)
        """, (title, description, reminder_time.isoformat(), datetime.now().isoformat(), user_id))
        
        reminder_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Added reminder: {reminder_id} - {title}")
        
        return json.dumps({
            "success": True,
            "message": "Reminder added successfully and saved to database",
            "reminder": {
                "id": reminder_id,
                "title": title,
                "description": description,
                "datetime": reminder_time.isoformat(),
                "created_at": datetime.now().isoformat()
            }
        }, indent=2)
        
    except ValueError as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)
    except Exception as e:
        logger.error(f"Error adding reminder: {e}")
        return json.dumps({
            "success": False,
            "error": f"Failed to add reminder: {str(e)}"
        }, indent=2)


@mcp.tool()
def list_reminders(include_completed: str = "false", user_id: str = "default"):
    """List all reminders, optionally include completed ones (true/false)"""
    try:
        show_completed = include_completed.lower() == "true"
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if show_completed:
            cursor.execute("""
                SELECT * FROM reminders 
                WHERE user_id = ?
                ORDER BY reminder_datetime ASC
            """, (user_id,))
        else:
            cursor.execute("""
                SELECT * FROM reminders 
                WHERE completed = 0 AND user_id = ?
                ORDER BY reminder_datetime ASC
            """, (user_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        reminders = []
        for row in rows:
            reminders.append({
                "id": row["id"],
                "title": row["title"],
                "description": row["description"],
                "datetime": row["reminder_datetime"],
                "completed": bool(row["completed"]),
                "notified": bool(row["notified"]),
                "created_at": row["created_at"],
                "completed_at": row["completed_at"]
            })
        
        if not reminders:
            return json.dumps({
                "success": True,
                "message": "No reminders found",
                "reminders": []
            }, indent=2)
        
        return json.dumps({
            "success": True,
            "count": len(reminders),
            "reminders": reminders
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error listing reminders: {e}")
        return json.dumps({
            "success": False,
            "error": f"Failed to list reminders: {str(e)}"
        }, indent=2)


@mcp.tool()
def get_upcoming_reminders(hours: str = "24", user_id: str = "default"):
    """Get reminders due within the next N hours (default 24)"""
    try:
        hours_int = int(hours)
        now = datetime.now()
        future_time = now + timedelta(hours=hours_int)
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM reminders
            WHERE completed = 0 
            AND user_id = ?
            AND reminder_datetime BETWEEN ? AND ?
            ORDER BY reminder_datetime ASC
        """, (user_id, now.isoformat(), future_time.isoformat()))
        
        rows = cursor.fetchall()
        conn.close()
        
        upcoming = []
        for row in rows:
            reminder_dt = datetime.fromisoformat(row["reminder_datetime"])
            time_until = reminder_dt - now
            hours_until = time_until.total_seconds() / 3600
            
            upcoming.append({
                "id": row["id"],
                "title": row["title"],
                "description": row["description"],
                "datetime": row["reminder_datetime"],
                "hours_until": round(hours_until, 1),
                "notified": bool(row["notified"])
            })
        
        return json.dumps({
            "success": True,
            "count": len(upcoming),
            "time_window_hours": hours_int,
            "reminders": upcoming
        }, indent=2)
        
    except ValueError:
        return json.dumps({
            "success": False,
            "error": "Hours must be a valid number"
        }, indent=2)
    except Exception as e:
        logger.error(f"Error getting upcoming reminders: {e}")
        return json.dumps({
            "success": False,
            "error": f"Failed to get upcoming reminders: {str(e)}"
        }, indent=2)


@mcp.tool()
def check_overdue_reminders(user_id: str = "default"):
    """Check for overdue reminders that need immediate attention"""
    try:
        now = datetime.now()
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM reminders
            WHERE completed = 0 
            AND user_id = ?
            AND reminder_datetime < ?
            ORDER BY reminder_datetime ASC
        """, (user_id, now.isoformat()))
        
        rows = cursor.fetchall()
        conn.close()
        
        overdue = []
        for row in rows:
            reminder_dt = datetime.fromisoformat(row["reminder_datetime"])
            time_overdue = now - reminder_dt
            hours_overdue = time_overdue.total_seconds() / 3600
            
            overdue.append({
                "id": row["id"],
                "title": row["title"],
                "description": row["description"],
                "datetime": row["reminder_datetime"],
                "hours_overdue": round(hours_overdue, 1),
                "notified": bool(row["notified"])
            })
        
        if not overdue:
            return json.dumps({
                "success": True,
                "message": "No overdue reminders",
                "reminders": []
            }, indent=2)
        
        return json.dumps({
            "success": True,
            "count": len(overdue),
            "message": f"ALERT: You have {len(overdue)} overdue reminder(s)!",
            "reminders": overdue
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error checking overdue reminders: {e}")
        return json.dumps({
            "success": False,
            "error": f"Failed to check overdue reminders: {str(e)}"
        }, indent=2)


@mcp.tool()
def complete_reminder(reminder_id: str, user_id: str = "default"):
    """Mark a reminder as completed by its ID"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE reminders 
            SET completed = 1, completed_at = ?
            WHERE id = ? AND user_id = ?
        """, (datetime.now().isoformat(), int(reminder_id), user_id))
        
        if cursor.rowcount == 0:
            conn.close()
            return json.dumps({
                "success": False,
                "error": f"Reminder with ID {reminder_id} not found"
            }, indent=2)
        
        conn.commit()
        
        cursor.execute("SELECT * FROM reminders WHERE id = ?", (int(reminder_id),))
        row = cursor.fetchone()
        conn.close()
        
        logger.info(f"Completed reminder: {reminder_id}")
        
        return json.dumps({
            "success": True,
            "message": "Reminder marked as completed in database",
            "reminder_id": reminder_id
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error completing reminder: {e}")
        return json.dumps({
            "success": False,
            "error": f"Failed to complete reminder: {str(e)}"
        }, indent=2)


@mcp.tool()
def delete_reminder(reminder_id: str, user_id: str = "default"):
    """Delete a reminder by its ID"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM reminders WHERE id = ? AND user_id = ?", (int(reminder_id), user_id))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return json.dumps({
                "success": False,
                "error": f"Reminder with ID {reminder_id} not found"
            }, indent=2)
        
        cursor.execute("DELETE FROM reminders WHERE id = ? AND user_id = ?", (int(reminder_id), user_id))
        conn.commit()
        conn.close()
        
        logger.info(f"Deleted reminder: {reminder_id}")
        
        return json.dumps({
            "success": True,
            "message": "Reminder deleted permanently from database",
            "reminder_id": reminder_id
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error deleting reminder: {e}")
        return json.dumps({
            "success": False,
            "error": f"Failed to delete reminder: {str(e)}"
        }, indent=2)


@mcp.tool()
def search_reminders(query: str, user_id: str = "default"):
    """Search reminders by title or description"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM reminders
            WHERE user_id = ?
            AND (title LIKE ? OR description LIKE ?)
            ORDER BY reminder_datetime ASC
        """, (user_id, f"%{query}%", f"%{query}%"))
        
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            results.append({
                "id": row["id"],
                "title": row["title"],
                "description": row["description"],
                "datetime": row["reminder_datetime"],
                "completed": bool(row["completed"]),
                "notified": bool(row["notified"])
            })
        
        if not results:
            return json.dumps({
                "success": True,
                "message": f"No reminders found matching '{query}'",
                "reminders": []
            }, indent=2)
        
        return json.dumps({
            "success": True,
            "count": len(results),
            "query": query,
            "reminders": results
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error searching reminders: {e}")
        return json.dumps({
            "success": False,
            "error": f"Failed to search reminders: {str(e)}"
        }, indent=2)


@mcp.tool()
def get_reminder_stats(user_id: str = "default"):
    """Get statistics about all reminders"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM reminders WHERE user_id = ?", (user_id,))
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM reminders WHERE completed = 1 AND user_id = ?", (user_id,))
        completed = cursor.fetchone()[0]
        
        now = datetime.now()
        cursor.execute("""
            SELECT COUNT(*) FROM reminders 
            WHERE completed = 0 AND user_id = ? AND reminder_datetime < ?
        """, (user_id, now.isoformat()))
        overdue = cursor.fetchone()[0]
        
        future_24h = (now + timedelta(hours=24)).isoformat()
        cursor.execute("""
            SELECT COUNT(*) FROM reminders 
            WHERE completed = 0 AND user_id = ? 
            AND reminder_datetime BETWEEN ? AND ?
        """, (user_id, now.isoformat(), future_24h))
        upcoming_24h = cursor.fetchone()[0]
        
        conn.close()
        
        return json.dumps({
            "success": True,
            "stats": {
                "total_reminders": total,
                "completed": completed,
                "pending": total - completed,
                "overdue": overdue,
                "upcoming_24h": upcoming_24h
            }
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return json.dumps({
            "success": False,
            "error": f"Failed to get statistics: {str(e)}"
        }, indent=2)


if __name__ == "__main__":
    logger.info("Initializing Xiaozhi Reminder Server with Database...")
    init_database()
    logger.info("Starting MCP server...")
    mcp.run(transport="stdio")

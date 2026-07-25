import sqlite3
import os

os.makedirs("database", exist_ok=True)

conn = sqlite3.connect("database/game.db")

cur = conn.cursor()

# ------------------------
# Player
# ------------------------

cur.execute("""
CREATE TABLE IF NOT EXISTS players(

player_id TEXT PRIMARY KEY,

player_name TEXT,

role TEXT,

point INTEGER DEFAULT 100,

player_luck INTEGER DEFAULT 0,

today_free INTEGER DEFAULT 2,

today_play INTEGER DEFAULT 0,

total_play INTEGER DEFAULT 0,

season_point INTEGER DEFAULT 0,

lifetime_point INTEGER DEFAULT 0

)
""")

# ------------------------
# History
# ------------------------

cur.execute("""
CREATE TABLE IF NOT EXISTS history(

id INTEGER PRIMARY KEY AUTOINCREMENT,

player_id TEXT,

result TEXT,

score INTEGER,

time TIMESTAMP DEFAULT CURRENT_TIMESTAMP

)
""")

conn.commit()

conn.close()

print("Database Ready")
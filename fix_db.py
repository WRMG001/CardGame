import sqlite3

# เชื่อมต่อฐานข้อมูล SQLite (เปลี่ยนชื่อไฟล์ตามที่คุณใช้จริง เช่น database.db หรือ game.db)
conn = sqlite3.connect("database.db")
cursor = conn.cursor()

try:
    # เพิ่มคอลัมน์ last_play_date เข้าตาราง players
    cursor.execute("ALTER TABLE players ADD COLUMN last_play_date TEXT;")
    conn.commit()
    print("✅ เพิ่มคอลัมน์ last_play_date เรียบร้อยแล้ว!")
except sqlite3.OperationalError as e:
    print(f"⚠️ เกิดข้อผิดพลาดหรือมีคอลัมน์นี้อยู่แล้ว: {e}")
finally:
    conn.close()

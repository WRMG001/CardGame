import sqlite3

# ⚠️ อย่าลืมเช็กชื่อไฟล์ DB ตรงนี้ให้ตรงกับของคุณ เช่น database.db / game.db / instance/game.db
DB_NAME = "database.db" 

def fix_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        # คำสั่งเพิ่มคอลัมน์ last_play_date เข้าตาราง players
        cursor.execute("ALTER TABLE players ADD COLUMN last_play_date TEXT;")
        conn.commit()
        print("✅ เพิ่มคอลัมน์ last_play_date สำเร็จแล้ว!")
    except sqlite3.OperationalError as e:
        print(f"⚠️ การอัปเดต DB: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    fix_database()

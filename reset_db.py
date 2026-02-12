
import sqlite3
from db.schema import initialise_database, DB_PATH

def reset_trade_log():
    conn = sqlite3.connect(DB_PATH)
    try:
        # Drop old table
        conn.execute("DROP TABLE IF EXISTS trade_log")
        print("Dropped old trade_log table.")
    except Exception as e:
        print(f"Error dropping table: {e}")
    finally:
        conn.close()
        
    # Re-create with new schema
    initialise_database()

if __name__ == "__main__":
    reset_trade_log()

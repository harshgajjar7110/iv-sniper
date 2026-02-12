import sqlite3
import pandas as pd
from db.connection import DB_PATH

def main():
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM trade_log ORDER BY id DESC", conn)
        conn.close()
        
        if df.empty:
            print("No trades found in trade_log.")
        else:
            print(f"Found {len(df)} trades:")
            print(df.to_string())
            
    except Exception as e:
        print(f"Error reading DB: {e}")

if __name__ == "__main__":
    main()

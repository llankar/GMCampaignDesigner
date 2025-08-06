import sqlite3

def print_db_info(db_file):
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row  # Allow column access by name
    cursor = conn.cursor()
    
    # Get list of tables in the database.
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print("Tables in the database:")
    for table in tables:
        table_name = table[0]
        print(f"\nTable: {table_name}")
        
        # Get column info.
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        col_names = [col["name"] for col in columns]
        print("Columns:", col_names)
        
        # Get up to 5 rows from the table.
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
        rows = cursor.fetchall()
        for row in rows:
            row_dict = {key: row[key] for key in row.keys()}
            print(row_dict)
        print("-" * 40)
    
    conn.close()

if __name__ == "__main__":
    db_file = "campaign.db"  # Adjust path if necessary.
    print_db_info(db_file)

import sqlite3

def create_pre_tables(db_name):
    try:
        # Connect to the SQLite database
        connection = sqlite3.connect(db_name)
        cursor = connection.cursor()

        # Create pre_donors table with same structure as donors
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pre_donors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT,
                email TEXT,
                blood_type TEXT,
                organ TEXT,
                age INTEGER,
                longitude REAL,
                latitude REAL
            )
        ''')

        # Create pre_recipients table with same structure as recipients
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pre_recipients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT,
                email TEXT,
                blood_type TEXT,
                needed_organ TEXT,
                urgency_level INTEGER,
                age INTEGER,
                longitude REAL,
                latitude REAL
            )
        ''')

      
        # Commit the changes
        connection.commit()
        print("Pre-tables created successfully!")

    except sqlite3.Error as e:
        print(f"An error occurred: {e}")

    finally:
        # Close the connection
        if connection:
            connection.close()

if __name__ == "__main__":
    database_name = "organ_donation.db"
    create_pre_tables(database_name)
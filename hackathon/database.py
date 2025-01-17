import sqlite3

# SQLite database file name
DB_FILE = 'organ_donation.db'

def create_tables():
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password TEXT,
            user_type TEXT
        )
    ''')

    # Create donors table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS donors (
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

    # Create recipients table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recipients (
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

    # Create notifications table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            type TEXT,
            FOREIGN KEY (user_id) REFERENCES recipients(id)
        )
    ''')

    # Create requests table
    cursor.execute('''CREATE TABLE IF NOT EXISTS requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        donor_id INTEGER NOT NULL,
        recipient_id INTEGER NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (donor_id) REFERENCES donors(id),
        FOREIGN KEY (recipient_id) REFERENCES recipients(id)
    )''')

    connection.commit()
    cursor.close()
    connection.close()
    print("Database and tables created successfully.")

if __name__ == '__main__':
    create_tables()

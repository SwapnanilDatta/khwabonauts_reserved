import sqlite3

# Connect to the SQLite database (or create it if it doesn't exist)
conn = sqlite3.connect('organn_donation.db')

# Create a cursor object to execute SQL commands
cursor = conn.cursor()

# SQL command to delete the 'requests' table
drop_table_query = "DROP TABLE IF EXISTS requests;"

# Execute the SQL command
cursor.execute(drop_table_query)

# Commit the transaction
conn.commit()

# Close the connection
conn.close()

print("Table 'requests' deleted successfully.")
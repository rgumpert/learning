import sqlite3

conn = sqlite3.connect("patients.db")
cursor = conn.cursor()

cursor.execute("""
	CREATE TABLE IF NOT EXISTS patients (
		mrn TEXT PRIMARY KEY,
		name TEXT,
		age INTEGER,
		a1c REAL
	)
""")

cursor.execute("INSERT INTO patients VALUES ('001', 'Garcia, Maria', 67, 8.2)")
cursor.execute("INSERT INTO patients VALUES ('002', 'Johnson, Tom', 54, 7.1)")
cursor.execute("INSERT INTO patients VALUES ('003', 'Patel, Anita', 71, 9.4)")
cursor.execute("INSERT INTO patients VALUES ('004', 'Lee, James', 48, 6.8)")

conn.commit()
conn.close()

print("Database created.")


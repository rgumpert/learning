import sqlite3

conn = sqlite3.connect("patients.db")
cursor = conn.cursor()

cursor.execute("SELECT mrn, name, age, a1c FROM patients")
rows = cursor.fetchall()

patients = []
for row in rows:
	patients.append({
		"mrn": row[0],
		"name": row[1],
		"age": row[2],
		"a1c": row[3]
	})

conn.close()

for patient in patients:
	if patient["a1c"] > 9.0:
		print(f"{patient['name']} - urgent follow-up. A1c: {patient['a1c']}")
	elif patient["a1c"] > 7.5:
		print(f"{patient['name']} - routine follow-up. A1c: {patient['a1c']}")
	else:
		print(f"{patient['name']} - at goal. A1c: {patient['a1c']}")







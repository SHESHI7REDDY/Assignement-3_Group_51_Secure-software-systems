import sqlite3

conn = sqlite3.connect("ballots.db")
cursor = conn.cursor()

cursor.execute("SELECT id, election_id, encrypted_ballot FROM ballots")
rows = cursor.fetchall()

for row in rows:
    print("Ballot ID:", row[0])
    print("Election ID:", row[1])
    print("Encrypted ballot:", row[2])
    print("-" * 60)

conn.close()
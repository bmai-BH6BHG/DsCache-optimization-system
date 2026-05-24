import sqlite3, os, sys

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'cache_l2.db')
print("Path:", db_path)
print("Exists:", os.path.exists(db_path))
if not os.path.exists(db_path):
    print("DB NOT FOUND!")
    sys.exit(1)

print("Size:", os.path.getsize(db_path))
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", [t[0] for t in tables])

for t in tables:
    cursor.execute("SELECT COUNT(*) FROM [{}]".format(t[0]))
    n = cursor.fetchone()[0]
    print("  {}: {} rows".format(t[0], n))
    if n > 0:
        cursor.execute("SELECT * FROM [{}] LIMIT 3".format(t[0]))
        for row in cursor.fetchall():
            print("    ", str(row)[:100])

conn.close()

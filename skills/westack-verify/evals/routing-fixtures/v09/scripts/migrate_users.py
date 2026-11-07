import csv
import sqlite3
import sys


def migrate(src_csv, db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, email TEXT UNIQUE)")
    with open(src_csv, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            conn.execute("INSERT OR IGNORE INTO users (id, email) VALUES (?, ?)", (row["id"], row["email"]))
    conn.commit()
    return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


if __name__ == "__main__":
    print(migrate(sys.argv[1], sys.argv[2]))

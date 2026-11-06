import sqlite3
import threading


def worker(path, rows):
    conn = sqlite3.connect(path)
    for row in rows:
        conn.execute("INSERT INTO items (name) VALUES (?)", (row,))
        conn.commit()
    conn.close()


def run(path, rows, threads=8):
    chunks = [rows[i::threads] for i in range(threads)]
    pool = [threading.Thread(target=worker, args=(path, chunk)) for chunk in chunks]
    for thread in pool:
        thread.start()
    for thread in pool:
        thread.join()

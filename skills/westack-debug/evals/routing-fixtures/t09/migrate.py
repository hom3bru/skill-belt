import pathlib
import sqlite3


def apply_all(db_path, folder="migrations"):
    conn = sqlite3.connect(db_path)
    for path in sorted(pathlib.Path(folder).glob("*.sql")):
        conn.executescript(path.read_text(encoding="utf-8"))
    conn.commit()
    return conn

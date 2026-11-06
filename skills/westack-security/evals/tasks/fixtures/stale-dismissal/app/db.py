# std-db-3p5
import sqlite3

DB = "app.db"


def query(sql, params=()):
    with sqlite3.connect(DB) as conn:
        return conn.execute(sql, params).fetchall()


def execute(sql, params=()):
    with sqlite3.connect(DB) as conn:
        conn.execute(sql, params)

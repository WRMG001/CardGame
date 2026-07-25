import sqlite3

DB = "database/game.db"


def connect():
    return sqlite3.connect(DB)
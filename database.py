import sqlite3


DATABASE = "noteswap.db"


def get_db_connection():

    connection = sqlite3.connect(DATABASE)

    connection.row_factory = sqlite3.Row

    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def create_tables():

    connection = get_db_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            subject TEXT NOT NULL,
            description TEXT,
            filename TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (user_id)
            REFERENCES users(id)
            ON DELETE CASCADE
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            note_id INTEGER NOT NULL,

            UNIQUE(user_id, note_id),

            FOREIGN KEY (user_id)
            REFERENCES users(id)
            ON DELETE CASCADE,

            FOREIGN KEY (note_id)
            REFERENCES notes(id)
            ON DELETE CASCADE
        )
    """)

    connection.commit()

    connection.close()
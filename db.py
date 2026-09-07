import sqlite3
import os

# Путь к базе данных
DB_PATH = "/data/game.db" if os.path.exists("/data") else "game.db"


def get_connection():
    """Создаёт соединение с базой данных."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Создаёт таблицы, если их нет."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS players (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            current_scene TEXT DEFAULT 's00',
            choices TEXT DEFAULT '',
            losses INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def get_player(user_id):
    """Возвращает данные игрока или None."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM players WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def create_player(user_id, username):
    """Создаёт нового игрока."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO players (user_id, username, current_scene) VALUES (?, ?, 's00')",
        (user_id, username)
    )
    conn.commit()
    conn.close()


def update_player(user_id, **kwargs):
    """Обновляет поля игрока."""
    if not kwargs:
        return
    conn = get_connection()
    cur = conn.cursor()
    fields = ", ".join([f"{key} = ?" for key in kwargs.keys()])
    values = list(kwargs.values()) + [user_id]
    cur.execute(f"UPDATE players SET {fields} WHERE user_id = ?", values)
    conn.commit()
    conn.close()


def record_choice(user_id, key):
    """Записывает выбор игрока на развилке."""
    player = get_player(user_id)
    if player is None:
        return
    choices = player.get("choices", "") or ""
    if key not in choices:
        choices = choices + "," + key if choices else key
        update_player(user_id, choices=choices)


def increment_losses(user_id):
    """Увеличивает счётчик проигранных интерактивов."""
    player = get_player(user_id)
    if player is None:
        return
    new_losses = (player.get("losses") or 0) + 1
    update_player(user_id, losses=new_losses)


def delete_player(user_id):
    """Удаляет запись игрока (для рестарта)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM players WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

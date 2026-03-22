import psycopg2
import os
from datetime import datetime

DB_URL = os.environ.get("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DB_URL)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            date TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def add_expense(user_id, amount, category, description=""):
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        INSERT INTO expenses (user_id, amount, category, description, date)
        VALUES (%s, %s, %s, %s, %s)
    ''', (user_id, amount, category, description, datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    conn.close()

def get_expenses(user_id, period="month"):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now()
    if period == "month":
        start = now.strftime("%Y-%m-01")
    elif period == "week":
        from datetime import timedelta
        start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
    else:
        start = "2000-01-01"
    c.execute('''
        SELECT amount, category, description, date
        FROM expenses
        WHERE user_id = %s AND date >= %s
        ORDER BY date DESC
    ''', (user_id, start))
    rows = c.fetchall()
    conn.close()
    return rows

def get_summary(user_id, period="month"):
    rows = get_expenses(user_id, period)
    summary = {}
    total = 0
    for amount, category, _, _ in rows:
        summary[category] = summary.get(category, 0) + amount
        total += amount
    return summary, total
    

import sqlite3
import json
from datetime import datetime, timedelta
from config import DB_FILE

class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        
        # User Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                credits REAL DEFAULT 0,
                membership_type TEXT DEFAULT 'none',
                expiry_date DATETIME,
                is_admin BOOLEAN DEFAULT 0
            )
        ''')
        
        # Accounts Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                session_string TEXT,
                phone TEXT,
                username TEXT,
                device_data TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Tasks Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                target TEXT,
                reports_requested INTEGER,
                reports_done INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        self.conn.commit()

    # --- User Management ---
    
    def get_user(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        return cursor.fetchone()

    def add_user(self, user_id, is_admin=False):
        cursor = self.conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO users (user_id, is_admin) VALUES (?, ?)', (user_id, 1 if is_admin else 0))
        self.conn.commit()

    def update_membership(self, user_id, plan_type, credits):
        expiry_days = {"weekly": 7, "monthly": 30, "yearly": 365}
        days = expiry_days.get(plan_type.lower(), 0)
        expiry_date = datetime.now() + timedelta(days=days)
        
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET membership_type = ?, expiry_date = ?, credits = credits + ? 
            WHERE user_id = ?
        ''', (plan_type, expiry_date.strftime('%Y-%m-%d %H:%M:%S'), credits, user_id))
        
        if cursor.rowcount == 0:
            cursor.execute('INSERT INTO users (user_id, membership_type, expiry_date, credits) VALUES (?, ?, ?, ?)',
                           (user_id, plan_type, expiry_date.strftime('%Y-%m-%d %H:%M:%S'), credits))
        
        self.conn.commit()

    def set_user_credits(self, user_id, credits):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE users SET credits = ? WHERE user_id = ?', (credits, user_id))
        self.conn.commit()

    def get_all_users(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT user_id FROM users')
        return [row[0] for row in cursor.fetchall()]

    def is_member(self, user_id):
        user = self.get_user(user_id)
        if not user: return False
        
        # Admin is always member
        if user[4]: return True
        
        if user[2] == 'none': return False
        
        expiry = datetime.strptime(user[3], '%Y-%m-%d %H:%M:%S')
        return expiry > datetime.now()

    # --- Account Management ---

    def add_account(self, user_id, session, phone, username, device):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO accounts (user_id, session_string, phone, username, device_data)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, session, phone, username, json.dumps(device)))
        self.conn.commit()

    def get_user_accounts(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM accounts WHERE user_id = ?', (user_id,))
        rows = cursor.fetchall()
        accounts = []
        for row in rows:
            accounts.append({
                "id": row[0],
                "session": row[2],
                "phone": row[3],
                "username": row[4],
                "device": json.loads(row[5])
            })
        return accounts

    def remove_account(self, acc_id, user_id):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM accounts WHERE id = ? AND user_id = ?', (acc_id, user_id))
        self.conn.commit()

    # --- Task Management ---

    def create_task(self, user_id, target, reports_requested):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO tasks (user_id, target, reports_requested)
            VALUES (?, ?, ?)
        ''', (user_id, target, reports_requested))
        self.conn.commit()
        return cursor.lastrowid

    def update_task_progress(self, task_id, reports_done, status='running'):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE tasks SET reports_done = ?, status = ? WHERE id = ?', (reports_done, status, task_id))
        self.conn.commit()

    def get_active_tasks(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM tasks WHERE user_id = ? AND status = "running"', (user_id,))
        rows = cursor.fetchall()
        tasks = []
        for row in rows:
            tasks.append({
                "id": row[0],
                "target": row[2],
                "requested": row[3],
                "done": row[4],
                "status": row[5]
            })
        return tasks

    def update_task_status(self, task_id, status):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE tasks SET status = ? WHERE id = ?', (status, task_id))
        self.conn.commit()

db = DatabaseManager()

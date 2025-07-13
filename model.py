import sqlite3
import hashlib
from datetime import datetime

class chat_db:

    def __init__(self):
        self.connection = sqlite3.connect('chatroom.db')
        self.cursor = self.connection.cursor()
        self.cursor.execute("""CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT UNIQUE NOT NULL,
                            password TEXT NOT NULL,
                            creation_time TEXT NOT NULL)""")
        self.cursor.execute("""CREATE TABLE IF NOT EXISTS messages (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            content TEXT NOT NULL,
                            timestamp TEXT NOT NULL,
                            FOREIGN KEY (user_id) REFERENCES users (id)
                            )""")      
        self.connection.commit()


    def create_user(self, username, password):
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        creation_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            self.cursor.execute("INSERT INTO users (username, password, creation_time) VALUES (?, ?, ?)",
                                (username, hashed_password, creation_time))
            self.connection.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def authenticate_user(self, username, password):
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        self.cursor.execute("SELECT id, username FROM users WHERE username = ? AND password = ?",
                            (username, hashed_password))
        this_user = self.cursor.fetchall()
        return this_user
    
    def get_user(self, username):
        self.cursor.execute("SELECT id FROM users WHERE username = ? ", (username,))
        this_user = self.cursor.fetchall()
        return this_user    

    def save_message(self, user_id, content, timestamp=None):
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cursor.execute("INSERT INTO messages (user_id, content, timestamp) VALUES (?, ?, ?)",
                            (user_id, content, timestamp))
        self.connection.commit()

    def get_message_by_id(self, message_id):
        self.cursor.execute("SELECT id, user_id, content, timestamp FROM messages WHERE id = ?", (message_id,))
        return self.cursor.fetchone()

    def get_message(self, limit=100):
        try:
            # Ensure proper parameter passing (note the comma after limit)
            self.cursor.execute("""
                SELECT messages.id, users.username, messages.content, messages.timestamp
                FROM messages JOIN users ON messages.user_id = users.id
                ORDER BY messages.timestamp DESC
                LIMIT ?
            """, (limit,))  # The comma makes this a tuple
            
            messages = self.cursor.fetchall()
            return [{
                'id': msg[0],
                'username': msg[1],
                'content': msg[2],
                'timestamp': msg[3]
            } for msg in messages]
        except sqlite3.Error as e:
            print(f"Database error: {str(e)}")
            return None
        
    def delete_message(self, message_id):
        try:
            self.cursor.execute("DELETE FROM messages WHERE id = ?", (message_id,))
            self.connection.commit()
            return self.cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Database error in delete_message: {e}")
            return False

    def edit_message(self, message_id, new_content):
        try:
            self.cursor.execute(
                "UPDATE messages SET content = ? WHERE id = ?",
                (new_content, message_id)
            )
            self.connection.commit()
            return self.cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Database error in edit_message: {e}")
            return False
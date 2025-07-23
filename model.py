import sqlite3
import hashlib
from datetime import datetime
import os

class chat_db:

    def __init__(self):
        self.connection = sqlite3.connect('chatroom.db')
        self.cursor = self.connection.cursor()
        self.cursor.execute("PRAGMA foreign_keys = ON")
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
                            has_attachment BOOLEAN DEFAULT 0,
                            attachment_id INTEGER,
                            FOREIGN KEY (user_id) REFERENCES users (id),
                            FOREIGN KEY (attachment_id) REFERENCES attachments (id)
                            )""")
        self.cursor.execute("""CREATE TABLE IF NOT EXISTS attachments (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            file_name TEXT NOT NULL,
                            file_path TEXT NOT NULL,
                            file_size INTEGER NOT NULL,  
                            mime_type TEXT NOT NULL,
                            hash_sha256 TEXT NOT NULL,  
                            upload_time TEXT NOT NULL,
                            FOREIGN KEY (user_id) REFERENCES users(id)
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

    def get_message_by_id(self, message_id):
        self.cursor.execute("SELECT id, user_id, content, timestamp FROM messages WHERE id = ?", (message_id,))
        return self.cursor.fetchone()

    def save_message(self, user_id, content, timestamp=None, attachment_id=None):
        try:
            if timestamp is None:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
            content = content or ""

            has_attachment = 1 if attachment_id is not None else 0

            self.cursor.execute(
                "INSERT INTO messages (user_id, content, timestamp, has_attachment, attachment_id) VALUES (?, ?, ?, ?, ?)",
                (user_id, content, timestamp, has_attachment, attachment_id)
            )
            self.connection.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error is {e}")
            return False

    def save_attachment(self, user_id, file_name, file_path, file_size, mime_type, hash_sha256):
        upload_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            self.cursor.execute(
                "INSERT INTO attachments (user_id, file_name, file_path, file_size, mime_type, hash_sha256, upload_time) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, file_name, file_path, file_size, mime_type, hash_sha256, upload_time)
            )
            self.connection.commit()
            return self.cursor.lastrowid  # Return attachment ID on success
        except sqlite3.Error as e:
            print(f"[ERROR] Failed to save attachment: {e}")
            return None


    def get_message(self, limit=100):
        try:
            self.cursor.execute("""
                SELECT messages.id, users.username, messages.content, messages.timestamp,
                    messages.has_attachment, attachments.id, attachments.file_name, attachments.file_path, attachments.mime_type
                FROM messages
                JOIN users ON messages.user_id = users.id
                LEFT JOIN attachments ON messages.attachment_id = attachments.id
                ORDER BY messages.timestamp DESC
                LIMIT ?
            """, (limit,))
            
            messages = self.cursor.fetchall()
            result = []
            for msg in messages:
                msg_dict = {
                    'id': msg[0],
                    'username': msg[1],
                    'content': msg[2],
                    'timestamp': msg[3],
                    'has_attachment': bool(msg[4]),
                    'attachment': None
                }
                if msg[4]:
                    msg_dict['attachment'] = {
                        'id': msg[5],
                        'file_name': msg[6],
                        'file_path': msg[7],
                        'mime_type': msg[8],
                    }
                result.append(msg_dict)
            return result
        except sqlite3.Error as e:
            print(f"[ERROR] Failed to fetch messages: {e}")
            return []

        
    def delete_message(self, message_id):
        try:
            # Find attachment id and file path if message has attachment
            self.cursor.execute("""
                SELECT attachment_id FROM messages WHERE id = ?
            """, (message_id,))
            row = self.cursor.fetchone()
            if not row:
                print(f"[WARN] Message ID {message_id} not found.")
                return False
            
            attachment_id = row[0]

            # Delete message first
            self.cursor.execute("DELETE FROM messages WHERE id = ?", (message_id,))
            if self.cursor.rowcount == 0:
                print(f"[WARN] Message ID {message_id} could not be deleted.")
                return False
            
            # If there's an attachment, delete attachment record and file
            if attachment_id:
                self.cursor.execute("SELECT file_path FROM attachments WHERE id = ?", (attachment_id,))
                file_row = self.cursor.fetchone()
                if file_row:
                    file_path = file_row[0]
                    # Delete the file from disk if exists
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            print(f"[INFO] Deleted file: {file_path}")
                    except Exception as e:
                        print(f"[ERROR] Could not delete file {file_path}: {e}")

                # Delete attachment record from DB
                self.cursor.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
            
            self.connection.commit()
            return True

        except sqlite3.Error as e:
            print(f"[ERROR] Failed to delete message: {e}")
            return False

    def edit_message(self, message_id, new_content, new_attachment=None):

        try:
            # Fetch old attachment id and user_id for the message
            self.cursor.execute("SELECT attachment_id, user_id FROM messages WHERE id = ?", (message_id,))
            row = self.cursor.fetchone()
            if not row:
                print(f"[WARN] Message ID {message_id} not found.")
                return False

            old_attachment_id, user_id = row

            # If there is a new attachment, handle deleting old attachment and saving new
            if new_attachment:
                # Delete old attachment if exists
                if old_attachment_id:
                    self.cursor.execute("SELECT file_path FROM attachments WHERE id = ?", (old_attachment_id,))
                    file_row = self.cursor.fetchone()
                    if file_row:
                        file_path = file_row[0]
                        try:
                            if os.path.exists(file_path):
                                os.remove(file_path)
                                print(f"[INFO] Deleted old file: {file_path}")
                        except Exception as e:
                            print(f"[ERROR] Could not delete old file {file_path}: {e}")

                    self.cursor.execute("DELETE FROM attachments WHERE id = ?", (old_attachment_id,))
                
                # Save new attachment and get new ID
                new_attachment_id = self.save_attachment(
                    user_id=user_id,  # Pass user_id here
                    file_name=new_attachment['file_name'],
                    file_path=new_attachment['file_path'],
                    file_size=new_attachment['file_size'],
                    mime_type=new_attachment['mime_type'],
                    hash_sha256=new_attachment['hash_sha256']
                )
            else:
                new_attachment_id = old_attachment_id

            # Update the message content and attachment_id
            self.cursor.execute(
                "UPDATE messages SET content = ?, attachment_id = ?, has_attachment = ? WHERE id = ?",
                (new_content, new_attachment_id, 1 if new_attachment_id else 0, message_id)
            )
            self.connection.commit()
            return True

        except sqlite3.Error as e:
            print(f"[ERROR] Failed to edit message: {e}")
            return False

import model
import re
import tornado.web
import tornado.ioloop 
import tornado.websocket
from datetime import datetime
from tornado.escape import xhtml_escape
import os
import files
import hashlib
import mimetypes
import random
import json


class BaseHandler(tornado.web.RequestHandler):

    def get_current_user(self):
        return self.get_secure_cookie("user")
    def get_db(self):
        return model.chat_db() 
    def prepare(self):
        # Set JSON headers for API responses
        if self.request.path.startswith('/api/'):
            self.set_header('Content-Type', 'application/json')    
    
class MainHandler(BaseHandler):
    def get(self):
        if self.current_user:
            self.redirect('/chat')
        else:
            self.redirect('/login')

class LoginHandler(BaseHandler):

    async def get(self):
        error = self.get_argument("error", None)
        self.render("login.html", error=error)

    async def post(self):
        username = self.get_body_argument("username")
        password = self.get_body_argument("password")

        DB = self.get_db()
        user = DB.authenticate_user(username, password)
        if user:
            self.set_secure_cookie("user", username, httponly=True)
            self.redirect("/chat")

        else:
            self.render("login.html", error = "Invalid username or password")

class SignupHandler(BaseHandler):

    def check_password(self, password):
        
        check_len = bool(len(password)>=6)
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_number = any(c.isdigit() for c in password)
        has_special = bool(re.search(r'[!@#$%*?]', password))

        return {
        'is_valid': all([check_len, has_upper, has_lower, has_number, has_special]),
        'len_ok': check_len,
        'has_upper': has_upper,
        'has_lower': has_lower,
        'has_number': has_number,
        'has_special': has_special
        }

    async def get(self):
        error = self.get_argument("error", None)
        self.render("signup.html", error=error)

    async def post(self):
        username = self.get_body_argument("username")
        password = self.get_body_argument("password")

        if len(username) < 4:
            self.render("signup.html", error = "Your username must be 4 characters at least!")

        if not self.check_password(password)['len_ok']:
            self.render("signup.html", error = "Your password must be 6 characters at least!")
        elif not self.check_password(password)['has_upper']:
            self.render("signup.html", error = "Your password must contain an upper case")
        elif not self.check_password(password)['has_lower']:
            self.render("signup.html", error = "Your password must contain a lower case")
        elif not self.check_password(password)['has_number']:
            self.render("signup.html", error = "Your password must contain a number")
        elif not self.check_password(password)['has_special']:
            self.render("signup.html", error = "Your password must contain special characters [!@#$%*?]")

    
        DB = self.get_db()
        if DB.create_user(username, password):
            self.set_secure_cookie("user", username)
            self.set_status(201)
            self.redirect("/chat")
        else:
            self.set_status(400)
            self.render("signup.html", error = "username already exists!")

class LogoutHandler(BaseHandler):
    
    def get(self):
        self.clear_cookie("user")
        self.redirect("/login")

class MessageHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self):
        try:
            DB = self.get_db()
            messages = DB.get_message()
            
            # Debug output
            print(f"Retrieved messages: {messages}")
            
            if messages is None:
                raise Exception("Database query failed")
                
            self.render("chat.html",
                    messages=messages or [], 
                    current_user=self.current_user.decode("utf-8"),
                    error=None)
            
        except Exception as e:
            print(f"Error in chat handler: {str(e)}")
            self.render("error.html", 
                    error="Could not load chat messages",
                    current_user=self.current_user.decode("utf-8"))


    @tornado.web.authenticated
    async def post(self):
        try:
            content = xhtml_escape(self.get_argument("content")).strip()
            DB = self.get_db()
            username = self.current_user.decode("utf-8")
            user_id = DB.get_user(username)[0][0]
            attachment_id = None

            # Handle file attachment if present
            if 'attachment' in self.request.files and self.request.files["attachment"]:
                attachment_id = await self.process_attachment(self.request.files['attachment'][0], username)

            # Save message to database
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            DB.save_message(user_id, content, timestamp, attachment_id)

            # Prepare complete message data
            message_data = {
                "id": DB.cursor.lastrowid,
                "username": username,
                "content": content,
                "timestamp": timestamp,
                "has_attachment": bool(attachment_id),
                "attachment": {
                    "id": attachment_id,
                    "file_name": self.request.files['attachment'][0]['filename'] if attachment_id else None,
                    "mime_type": mimetypes.guess_type(self.request.files['attachment'][0]['filename'])[0] if attachment_id else None
                } if attachment_id else None
            }

            # Broadcast to all WebSocket clients
            WebSocketHandler.broadcast(message_data)

            self.set_status(201)
            self.write({
                "status": "success",
                "message": "Message sent successfully",
                "data": message_data
            })

        except ValueError as e:
                    self.set_status(400)
                    self.write({
                        "status": "error",
                        "message": str(e),
                        "type": "validation_error",
                        "details": {
                            "max_file_size": files.MAX_FILE_SIZES,
                            "allowed_types": files.ALLOWED_MIME_TYPES
                        } if "file" in str(e).lower() else None
                    })
        except Exception as e:
            self.set_status(500)
            self.write({
                "status": "error",
                "message": "Internal server error",
                "type": "server_error"
            })

    async def process_attachment(self, file_info, username):
        """Helper method to handle file uploads"""
        file_name = file_info['filename']
        file_body = file_info['body']
        
        mime_type, _ = mimetypes.guess_type(file_name)
        if not mime_type or mime_type not in files.ALLOWED_MIME_TYPES:
            raise ValueError("Unsupported file type")
        
        file_ext = os.path.splitext(file_name)[1].lower()
        if file_ext not in files.ALLOWED_MIME_TYPES.get(mime_type, []):
            raise ValueError("Invalid file extension for type")
        
        file_size = len(file_body)
        file_category = mime_type.split('/')[0]
        if (file_category in files.MAX_FILE_SIZES and 
            file_size > files.MAX_FILE_SIZES[file_category]):
            raise ValueError(f"File exceeds maximum size for {file_category}")
        
        file_hash = hashlib.sha256(file_body).hexdigest()
        upload_dir = self.settings['upload_dir']
        os.makedirs(upload_dir, exist_ok=True)
        
        unique_filename = f"{file_hash}{file_ext}"
        file_path = os.path.join(upload_dir, unique_filename)
        
        if not os.path.exists(file_path):
            with open(file_path, 'wb') as f:
                f.write(file_body)
        
        DB = self.get_db()
        user_id = DB.get_user(username)[0][0]
        return DB.save_attachment(
            user_id=user_id,
            file_name=file_name,
            file_path=file_path,
            file_size=file_size,
            mime_type=mime_type,
            hash_sha256=file_hash
        )

    @tornado.web.authenticated
    async def put(self, message_id):
        try:
            new_content = xhtml_escape(self.get_argument("new_content"))
            DB = self.get_db()
            username = self.current_user.decode("utf-8")
            user_id = DB.get_user(username)[0][0]

            message = DB.get_message_by_id(message_id)
            if not message or message[1] != user_id:
                raise Exception("Unauthorized or message not found")

            new_attachment = None
            if 'attachment' in self.request.files and self.request.files["attachment"]:
                file_info = self.request.files['attachment'][0]
                file_name = file_info['filename']
                file_body = file_info['body']
                
                # Determine MIME type based on file extension
                mime_type, _ = mimetypes.guess_type(file_name)
                if not mime_type:
                    raise ValueError("Could not determine file type")
                
                if mime_type not in files.ALLOWED_MIME_TYPES:
                    raise ValueError("File type not allowed")
                
                file_ext = os.path.splitext(file_name)[1].lower()
                if file_ext not in files.ALLOWED_MIME_TYPES.get(mime_type, []):
                    raise ValueError("File extension doesn't match MIME type")
                
                file_size = len(file_body)
                file_category = mime_type.split('/')[0]  # 'image', 'video', etc.
                if file_category in files.MAX_FILE_SIZES and file_size > files.MAX_FILE_SIZES[file_category]:
                    raise ValueError(f"File too large for type {file_category}")

                file_hash = hashlib.sha256(file_body).hexdigest()
                upload_dir = "uploads"
                if not os.path.exists(upload_dir):
                    os.makedirs(upload_dir)
                
                unique_filename = f"{file_hash}{file_ext}"
                file_path = os.path.join(upload_dir, unique_filename)
                
                if not os.path.exists(file_path):
                    with open(file_path, 'wb') as f:
                        f.write(file_body)
                
                new_attachment = {
                    'file_name': file_name,
                    'file_path': file_path,
                    'file_size': file_size,
                    'mime_type': mime_type,
                    'hash_sha256': file_hash
                }

            updated = DB.edit_message(
                message_id=message_id,
                new_content=new_content,
                new_attachment=new_attachment
            )
            
            if updated:
                self.set_status(204)
            else:
                raise Exception("Message not updated")
                
        except Exception as e:
            self.set_status(400)
            self.write({"status": "error", "message": str(e)})

    @tornado.web.authenticated
    async def delete(self, message_id):
        try:
            DB = self.get_db()
            username = self.current_user.decode("utf-8")
            user_id = DB.get_user(username)[0][0]

            message = DB.get_message_by_id(message_id)
            if not message or message[1] != user_id:
                raise Exception("Unauthorized or message not found")

            deleted = DB.delete_message(message_id)
            if deleted:
                self.set_status(204)
            else:
                raise Exception("Message not deleted")
        except Exception as e:
            self.set_status(400)
            self.write({"status": "error", "message": str(e)})


class WebSocketHandler(BaseHandler, tornado.websocket.WebSocketHandler):
    clients = set()

    async def open(self):
        if self.get_secure_cookie("user"):
            WebSocketHandler.clients.add(self)
            # Notify others about new connection
            self.broadcast_presence(self.current_user, "online")
        else:
            self.close()

    async def on_message(self, message):
        try:
            msg = json.loads(message)
            if msg.get('type') == 'typing':
                # Handle typing indicator
                self.broadcast_typing_status(
                    self.current_user.decode('utf-8'),
                    msg.get('is_typing', False)
                )
            elif msg.get('type') == 'read_receipt':
                # Handle read receipts
                self.broadcast_read_receipt(
                    self.current_user.decode('utf-8'),
                    msg.get('message_id')
                )
            # No message creation here!
        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(f"WebSocket error: {e}")

    def on_close(self):
        if self in WebSocketHandler.clients:
            WebSocketHandler.clients.remove(self)
            # Notify others about disconnection
            self.broadcast_presence(self.current_user, "offline")

    @classmethod
    def broadcast(cls, message):
        """More robust broadcasting"""
        dead_clients = []
        for client in cls.clients:
            try:
                client.write_message(message)
            except tornado.websocket.WebSocketClosedError:
                dead_clients.append(client)
        
        # Remove dead clients
        for client in dead_clients:
            cls.clients.remove(client)

    @classmethod
    def broadcast_typing_status(cls, username, is_typing):
        """For real-time typing indicators"""
        cls.broadcast({
            "type": "typing",
            "username": username,
            "is_typing": is_typing
        })

    @classmethod
    def broadcast_presence(cls, username, status):
        """For online/offline status"""
        cls.broadcast({
            "type": "presence",
            "username": username,
            "status": status
        })

    @classmethod
    def broadcast_read_receipt(cls, username, message_id):
        """For message read receipts"""
        cls.broadcast({
            "type": "read_receipt",
            "username": username,
            "message_id": message_id,
            "timestamp": datetime.now().isoformat()
        })


 
class AttachmentHandler(BaseHandler):
    async def get(self, attachment_id):
        try:
            DB = self.get_db()
            attachment = DB.cursor.execute("""
                SELECT file_name, file_path, mime_type, user_id 
                FROM attachments WHERE id = ?
            """, (attachment_id,)).fetchone()
            
            # Verify the requesting user has access to this file
            current_user = self.get_current_user().decode('utf-8')
            current_user_id = DB.get_user(current_user)[0][0]
            
            if not attachment or attachment[3] != current_user_id:
                raise tornado.web.HTTPError(404)
            
            # Stream the file instead of loading fully in memory
            self.set_header('Content-Type', attachment[2])
            self.set_header('Content-Disposition', 
                          f'attachment; filename="{attachment[0]}"')
            
            with open(attachment[1], 'rb') as f:
                while True:
                    chunk = f.read(4096)  # 4KB chunks
                    if not chunk:
                        break
                    self.write(chunk)
                    await self.flush()
        except Exception as e:
            print(f"Error!{e}")
            
            self.finish()

def make_app():
    # Initialize mimetypes
    mimetypes.init()

    return tornado.web.Application(
        [
            (r"/", MainHandler), 
            (r"/login", LoginHandler),
            (r"/signup", SignupHandler),
            (r"/logout", LogoutHandler),
            (r"/chat", MessageHandler),
            (r"/ws", WebSocketHandler), 
            (r"/api/messages/([0-9]+)", MessageHandler),
            (r"/api/messages", MessageHandler),
            (r"/attachments/([0-9]+)", AttachmentHandler)
        ],
        cookie_secret=str(random.randint(100000,999999)) + str(random.randint(100000,999999)),
        login_url="/login", 
        template_path="templates",
        static_path="static",
        upload_dir="uploads"
    )

if __name__ == "__main__":
    app = make_app()
    port = 8989  
    print(f"Starting server on port {port}")
    app.listen(port)
    tornado.ioloop.IOLoop.current().start()
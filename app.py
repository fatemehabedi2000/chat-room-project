import model
import re
import tornado.web
import tornado.ioloop 
import tornado.websocket
from datetime import datetime
from tornado.escape import xhtml_escape


class BaseHandler(tornado.web.RequestHandler):

    def get_current_user(self):
        return self.get_secure_cookie("user")
    def get_db(self):
        return model.chat_db() 
    
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
            content = xhtml_escape(self.get_argument("content"))
            DB = self.get_db()
            user = DB.authenticate_user(self.current_user.decode("utf-8"), "")[0]
            DB.save_message(user, content)
            self.set_status(201)
            self.write( {
                "Status": "Created",
                "message_id": DB.cursor.lastrowid
            })
        except Exception as e:
            self.set_status(400)
            self.write({
                "Status": "Not Created",
                "message": str(e)
            })


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

            updated = DB.edit_message(message_id, new_content)
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

    clients = set()  # list of connected users

    async def open(self):
        if self.get_secure_cookie("user"): # check login cookie
            WebSocketHandler.clients.add(self) 
        else:
            self.close()

    async def on_message(self, message):
        message = xhtml_escape(message)
        try:
            username = self.get_secure_cookie("user").decode('utf-8')
            
            DB = self.get_db()
            user = DB.get_user(username) 
            if not user:  # Check if user exists
                print(f"User {username} not found!")
                return
            
            user_id = user[0][0] 
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            DB.save_message(user_id, message.strip(), timestamp)
            
            msg_data = {
                "id": DB.cursor.lastrowid,  
                "username": username,
                "content": message,
                "timestamp": timestamp
            }
            #show to all
            for client in WebSocketHandler.clients:
                client.write_message(msg_data)

        except Exception as e:
            print(f"Error handling message: {e}")  

            
    def on_close(self):
        if self in WebSocketHandler.clients:
            WebSocketHandler.clients.remove(self)
 
     
import random

def make_app():

    return tornado.web.Application(
        [
            (r"/", MainHandler), 
            (r"/login", LoginHandler),
            (r"/signup", SignupHandler),
            (r"/logout", LogoutHandler),
            (r"/chat", MessageHandler),
            (r"/ws", WebSocketHandler), 
            (r"/api/messages/([0-9]+)", MessageHandler),
            (r"/api/messages", MessageHandler)
        ],
        cookie_secret=str(random.randint(100000,999999)) + str(random.randint(100000,999999)),
        login_url="/login", 
        template_path="templates",
        static_path="static"
    )

if __name__ == "__main__":
    app = make_app()
    app.listen(8989)
    tornado.ioloop.IOLoop.current().start()

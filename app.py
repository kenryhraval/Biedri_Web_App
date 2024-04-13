import os
import sqlite3

from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import login_required, error

app = Flask(__name__)

app.config['TEMPLATES_AUTO_RELOAD'] = True

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure SQLite database
db = os.path.join(os.path.dirname(__file__), "biedri.db")

# Function to get a database connection
def get_db_connection():
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    return conn

# this decorator ensures that responses from your Flask 
# application are not cached by clients or intermediary caches
@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

@app.route('/')
@login_required
def index():
    return render_template("index.html")

@app.route('/profile')
@login_required
def profile():
    return render_template("profile.html")

@app.route('/settings')
@login_required
def settings():
    return render_template("settings.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    session.clear()

    if request.method == "POST":
        username = request.form.get('username')
        password = request.form.get('password')

        if not username:
            return error("Must provide username", 400)

        elif not password:
            return error("Must provide password", 400)

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
        except sqlite3.Error as e:
            print(e)
            return error(f'System error', 500)

        try:
            rows = cursor.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            if not check_password_hash(rows["password"], password):
                return error("Invalid username and/or password", 400)

            session["user_id"] = rows["id"]
            return redirect("/")
        
        except sqlite3.Error as e:
            return error(f'Error: {e}', 500)
        
        finally:
            conn.close()

    return render_template("login.html")

@app.route('/register', methods=["GET", "POST"])
def register():
    if request.method == "POST":

        username = request.form.get('username')
        surname = request.form.get('surname')
        name = request.form.get('name')
        email = request.form.get('email')
        region = request.form.get('region')
        school = request.form.get('school')
        password = request.form.get('password')
        check = request.form.get('check')

        if not name:
            return error("must provide name", 400)

        elif not surname:
            return error("must provide surname", 400)

        elif not username:
            return error("must provide username", 400)

        elif not email:
            return error("must provide email", 400)
        
        elif not region:
            return error("must provide region", 400)
        
        elif not school:
            return error("must provide school", 400)
        
        elif not password or not check:
            return error("must provide password", 400)
  
        elif password != check:
            return error("passwords do not match", 400)

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
        except sqlite3.Error as e:
            return error(f'System error', 500)
        

        '''Using a UNIQUE constraint on the username and email columns 
        is a good practice to enforce uniqueness. However, you're already 
        checking for duplicate usernames and emails in your code before 
        inserting into the database, which is redundant. You can rely on 
        the database to enforce uniqueness with the constraint.'''
        # try:
        #     rows = cursor.execute("SELECT * FROM users WHERE username = ? OR email = ?", (username, email,))
        #     if rows.fetchone():
        #         return error("Username or email already taken", 400)
        # except sqlite3.Error as e:
        #     return error(f'System error', 500)
        

        hash = generate_password_hash(password)
        
        try:
            cursor.execute("INSERT INTO users (name, surname, username, email, password, region, school) VALUES (?, ?, ?, ?, ?, ?, ?);",
                                              (name, surname, username, email, hash,     region, school))
            conn.commit()

            user = cursor.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            session["user_id"] = user["id"]
            return redirect("/")
        
        except sqlite3.Error as e:
            return error(f'Error: {e}', 500)
        finally:
            conn.close()
        
    return render_template("register.html")

@app.route('/logout')
def logout():
    session.clear()
    return redirect("/")


if __name__ == '__main__':
    app.run(debug=True)
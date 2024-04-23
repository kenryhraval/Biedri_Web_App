import os
import sqlite3

from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from helpers import login_required, error

app = Flask(__name__)

app.config['TEMPLATES_AUTO_RELOAD'] = True

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure SQLite database
db = os.path.join(os.path.dirname(__file__), "biedri.db")


# manage picture files
UPLOAD_FOLDER = 'static/files'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Function to get a database connection
def get_db_connection():
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    return conn

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        items = cursor.execute("SELECT * FROM clubs").fetchall()
        return render_template("index.html", items=items)
    except sqlite3.Error as e:
        return error(f"{e}", 500)
    finally:
        conn.close()

@app.route('/club/<int:club_id>', methods=['GET', 'POST'])
def club_details(club_id):
    if request.method == 'POST':
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO applications (club_id, app_id) VALUES (?, ?)",
                                                     (club_id, session["user_id"],))
            conn.commit()
            return redirect("/") 
        except sqlite3.Error as e:
            return error(f"{e}", 500)
        finally:
            conn.close()
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        club = cursor.execute("SELECT * FROM clubs WHERE id = ?", (club_id,)).fetchone()
        
        applications = cursor.execute("SELECT * FROM applications WHERE app_id = ? AND club_id = ?", (session["user_id"], club_id,)).fetchone()
        applied = bool(applications)


        return render_template('club.html', club=club, applied=applied)
    except sqlite3.Error as e:
        return error(f"{e}", 500)
    finally:
        conn.close()


@app.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == "POST":
        name = request.form.get('name')
        description = request.form.get('description')
        category = request.form.get('category')
        goal = request.form.get('goal')
        school = request.form.get('school')

        if not name:
            return error("Must provide a name", 400)
        elif not description:
            return error("Must provide a description", 400)
        elif not category:
            return error("Must provide a category", 400)
        elif not goal:
            return error("Must provide a goal", 400)
        elif not school:
            return error("Must provide a school", 400)

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO clubs (name, description, category, leader_id, school, goal) VALUES (?, ?, ?, ?, ?, ?)",
                                              (name, description, category, session["user_id"], school, goal))
            conn.commit()
            return redirect("/") 
        except sqlite3.Error as e:
            return error(f"{e}", 500)
        finally:
            conn.close()

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        categories = [row['category'] for row in cursor.execute("SELECT category FROM categories").fetchall()]
        return render_template("create.html", categories=categories)
    except sqlite3.Error as e:
        return error(f"{e}", 500)
    finally:
        conn.close()
    


@app.route('/profile')
@login_required
def profile():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        user = cursor.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        joined = cursor.execute("""
                                    SELECT c.* 
                                    FROM clubs c 
                                    JOIN members m ON c.id = m.club_id 
                                    WHERE m.user_id = ?
                                """, (session["user_id"],)).fetchall()
        
        print(joined)

        owned = cursor.execute("SELECT * FROM clubs WHERE leader_id = ?", (session["user_id"],)).fetchall()

        return render_template("profile.html", user=user, joined = joined, owned = owned)
    except sqlite3.Error as e:
        return error(f"{e}", 500)
    finally:
        conn.close()
    

@app.route('/settings')
@login_required
def settings():
    if request.method == 'POST':
        picture = request.files.get('photo') # get the picture
        if not picture:
            return error("Must provide picture", 400)
        elif not allowed_file(picture.filename):
            return error("Invalid file type", 400)
        
        filename = secure_filename(picture.filename)
        picture.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

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
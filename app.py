import os
import sqlite3

from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from flask import url_for

from helpers import login_required, error, generate_slug

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
CLUB_PROFILE_PICTURES = os.path.join(app.config['UPLOAD_FOLDER'], 'club_profile_pictures')
USER_PROFILE_PICTURES = os.path.join(app.config['UPLOAD_FOLDER'], 'user_profile_pictures')


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
        query = """
            SELECT clubs.*, 
                   (SELECT COUNT(*) FROM members WHERE members.club_id = clubs.id) AS amount
            FROM clubs
            WHERE clubs.id NOT IN (SELECT club_id FROM members WHERE user_id = ?)
        """
        items = cursor.execute(query, (session["user_id"],)).fetchall()
        return render_template("index.html", items=items)
    except sqlite3.Error as e:
        return error(f"{e}", 500)
    finally:
        conn.close()

@app.route('/favourite', methods=['POST'])
@login_required
def favourite():
    try:
        club_id = request.form['club']
        slug = request.form['slug']
        conn = get_db_connection()
        cursor = conn.cursor()
        is_favorite = cursor.execute("SELECT * FROM favourites WHERE club_id = ? AND user_id = ?", (club_id, session["user_id"])).fetchone()
        if is_favorite:
            cursor.execute("DELETE FROM favourites WHERE club_id = ? AND user_id = ?", (club_id, session["user_id"]))
            conn.commit()
        else:
            cursor.execute("INSERT INTO favourites (club_id, user_id) VALUES (?, ?)", (club_id, session["user_id"]))
            conn.commit()
        return redirect(url_for('club_details', slug=slug))
    except sqlite3.Error as e:
        return error(f"{e}", 500)
    finally:
        conn.close()

"""
If you want to hide the slug from the URL, 
you can still pass it as a form parameter 
or in the query string instead of directly 
in the URL path (commented lines below)
"""	
@app.route('/club/<slug>', methods=['GET', 'POST'])
def club_details(slug):
    # slug = request.args.get('slug')
    # ...in the page that you can access the club details:
    # redirect_url = '/club?slug=' + item['slug']
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Fetch the internal club ID using the slug
        club = cursor.execute("SELECT * FROM clubs WHERE slug = ?", (slug,)).fetchone()
        if not club:
            return error("Club not found", 404)
        club_id = club['id']

        if request.method == 'POST':
            cursor.execute("INSERT INTO applications (club_id, app_id) VALUES (?, ?)",
                                                     (club_id, session["user_id"]))
            conn.commit()
            return redirect(url_for('club_details', slug=slug))

        applications = cursor.execute("SELECT * FROM applications WHERE app_id = ? AND club_id = ?", (session["user_id"], club_id)).fetchone()
        applied = bool(applications)
        
        members = cursor.execute("SELECT * FROM members WHERE club_id = ? AND user_id = ?", (club_id, session["user_id"])).fetchone()
        member = bool(members)

        favourite = cursor.execute("SELECT * FROM favourites WHERE user_id = ? AND club_id = ?", (session["user_id"], club_id,)).fetchone()
        favourites = bool(favourite)

        return render_template('club.html', club=club, applied=applied, member=member, members=members, favourites=favourites)
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
            slug = generate_slug(name)
            # Insert the new club into the clubs table
            cursor.execute("""
                INSERT INTO clubs (name, description, category, leader_id, school, goal, slug) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (name, description, category, session["user_id"], school, goal, slug))

             # Get the id of the newly inserted club
            club_id = cursor.lastrowid

            # Insert the current user as a member with the role "leader"
            cursor.execute("""
                INSERT INTO members (user_id, club_id, date, role) 
                VALUES (?, ?, datetime('now'), ?)
            """, (session["user_id"], club_id, "leader"))

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

@app.route('/edit_club', methods=['POST'])
@login_required
def edit_club():
    try:
        # Extract form data
        club_id = request.form['club_id']
        name = request.form['name']
        category = request.form['category']
        goal = request.form['goal']
        description = request.form['description']
        school = request.form['school']
        photo = request.files.get('photo')  # Use .get() to safely get the file input
        
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
        
        conn = get_db_connection()
        cursor = conn.cursor()

        # Update club details in the database
        cursor.execute("""
            UPDATE clubs 
            SET name=?, category=?, goal=?, description=?, school=?
            WHERE id=?
        """, (name, category, goal, description, school, club_id))
        
        # Handle photo upload if a file is provided
        if photo and allowed_file(photo.filename):
            photo_filename = secure_filename(photo.filename)
            photo_path = os.path.join(CLUB_PROFILE_PICTURES, photo_filename)
            photo.save(photo_path)
            cursor.execute("""
                UPDATE clubs 
                SET photo=? 
                WHERE id=?
            """, (photo_filename, club_id))
        elif photo:
            return error("Invalid file type", 400)

        conn.commit()
        
        return redirect("/profile")
        
    except sqlite3.Error as e:
        return error(f"{e}", 500)
    except Exception as e:
        return error(f"Unexpected error: {e}", 500)
    finally:
        conn.close()

@app.route('/edit', methods=['POST'])
def edit():  
    try:
        club_id = request.form['club']
        conn = get_db_connection()
        cursor = conn.cursor()
        club = cursor.execute("SELECT * FROM clubs WHERE id = ?", (club_id,)).fetchone()
        categories = [row['category'] for row in cursor.execute("SELECT category FROM categories").fetchall()]
        return render_template('edit.html', club=club, categories = categories)

    except sqlite3.Error as e:
        return error(f"{e}", 500)
    finally:
        conn.close()

@app.route('/modify_members', methods=['POST'])
def modify_members():
    member = request.form['member_id']
    action = request.form['action']
    club_id = request.form['club']

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if action == 'accept':
            cursor.execute("INSERT INTO members (user_id, club_id, date, role) VALUES (?, ?, ?, ?)", (member, club_id, date, "default"))
            cursor.execute("DELETE FROM applications WHERE app_id = ? AND club_id = ?", (member, club_id, ))
        elif action == 'reject':
            cursor.execute("DELETE FROM applications WHERE app_id = ? AND club_id = ?", (member, club_id, ))
        elif action == 'remove':
            cursor.execute("DELETE FROM members WHERE user_id = ? AND club_id = ?", (member, club_id, ))
        conn.commit()

        return redirect(url_for('members', club_id=club_id), code=307)
    except sqlite3.Error as e:
        return error(f"{e}", 500)
    finally:
        conn.close()

@app.route('/members', methods=['POST'])
def members():   
    try:
        club_id = request.form['club']
        conn = get_db_connection()
        cursor = conn.cursor()
        club = cursor.execute("SELECT * FROM clubs WHERE id = ?", (club_id,)).fetchone()
        
        applications = cursor.execute("""
            SELECT 
                applications.*, 
                users.* 
            FROM 
                applications 
            INNER JOIN 
                users ON applications.app_id = users.id 
            WHERE 
                applications.club_id = ?""", (club_id,)).fetchall()

        

        members = cursor.execute("""
            SELECT 
                members.*, 
                users.* 
            FROM 
                members 
            INNER JOIN 
                users ON members.user_id = users.id 
            WHERE 
                members.club_id = ?""", (club_id,)).fetchall()



        return render_template('members.html', club=club, applications = applications, members = members)
    except sqlite3.Error as e:
        return error(f"{e}", 500)
    finally:
        conn.close()

@app.route('/manage')
@login_required
def manage():
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
        

        owned = cursor.execute("SELECT * FROM clubs WHERE leader_id = ?", (session["user_id"],)).fetchall()

        return render_template("manage.html", user=user, joined = joined, owned = owned)
    except sqlite3.Error as e:
        return error(f"{e}", 500)
    finally:
        conn.close()
    
@app.route('/profile/<slug>')
@login_required
def profile(slug):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        user = cursor.execute("SELECT * FROM users WHERE slug = ?", (slug,)).fetchone()
        joined = cursor.execute("""
                                    SELECT c.* 
                                    FROM clubs c 
                                    JOIN members m ON c.id = m.club_id 
                                    WHERE m.user_id = ?
                                """, (user["id"],)).fetchall()
        

        owned = cursor.execute("SELECT * FROM clubs WHERE leader_id = ?", (user["id"],)).fetchall()

        return render_template("profile.html", user=user, joined=joined, owned=owned)
    except sqlite3.Error as e:
        return error(f"{e}", 500)
    finally:
        conn.close()


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        username = request.form.get('username')
        surname = request.form.get('surname')
        name = request.form.get('name')
        email = request.form.get('email')
        region = request.form.get('region')
        school = request.form.get('school')
        photo = request.files.get('photo')

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
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute("UPDATE users SET name=?, surname=?, username=?, email=?, region=?, school=?, last_edited=? WHERE id=?", (name, surname, username, email, region, school, date, session["user_id"],))
            
            # Handle photo upload if a file is provided
            if photo and allowed_file(photo.filename):
                photo_filename = secure_filename(photo.filename)
                photo_path = os.path.join(USER_PROFILE_PICTURES, photo_filename)
                photo.save(photo_path)
                cursor.execute("""
                    UPDATE users 
                    SET photo=? 
                    WHERE id=?
                """, (photo_filename, session["user_id"]))
            elif photo:
                return error("Invalid file type", 400)
            
            conn.commit()

            return redirect(url_for('index'))
        except sqlite3.Error as e:
            return error(f"{e}", 500)
        finally:
            conn.close()

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        user = cursor.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()  # Corrected syntax
        return render_template("settings.html", user=user)

    except sqlite3.Error as e:
        return error(f"{e}", 500)
    finally:
        conn.close()

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
            return error(f'System error', 500)

        try:
            rows = cursor.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            if not check_password_hash(rows["password"], password):
                return error("Invalid username and/or password", 400)

            session["user_id"] = rows["id"]
            session["slug"] = rows["slug"]
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
            slug = generate_slug(username)
            cursor.execute("INSERT INTO users (name, surname, username, email, password, region, school, slug) VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
                                              (name, surname, username, email, hash,     region, school, slug))
            conn.commit()

            user = cursor.execute("SELECT id, slug FROM users WHERE username = ?", (username,)).fetchone()
            session["user_id"] = user["id"]
            session["slug"] = user["slug"]
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
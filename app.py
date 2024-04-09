from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import login_required

app = Flask(__name__)

app.config['TEMPLATES_AUTO_RELOAD'] = True

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


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
def index():
    return render_template("profile.html")

@app.route('/settings')
@login_required
def index():
    return render_template("settings.html")

@app.route('/login')
def index():
    return render_template("login.html")


if __name__ == '__main__':
    app.run(debug=True)
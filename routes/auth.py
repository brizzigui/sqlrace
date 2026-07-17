from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from database import get_main_db

bp = Blueprint('auth', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'team_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'team_id' not in session:
            flash('Please log in first.', 'warning')
            return redirect(url_for('auth.login'))
        if not session.get('is_admin', False):
            flash('Access denied. Administrator privileges required.', 'danger')
            return redirect(url_for('contest.contests_list'))
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if 'team_id' in session:
        return redirect(url_for('contest.contests_list'))
        
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            flash('Username and password are required.', 'danger')
            return render_template('register.html')
            
        hashed_pw = generate_password_hash(password)
        
        try:
            with get_main_db() as cur:
                # Check duplicate
                cur.execute("SELECT id FROM teams WHERE username = %s;", (username,))
                if cur.fetchone():
                    flash('Team name is already registered. Please choose another one.', 'danger')
                    return render_template('register.html')
                    
                cur.execute("""
                INSERT INTO teams (username, password_hash, is_admin)
                VALUES (%s, %s, FALSE) RETURNING id;
                """, (username, hashed_pw))
                new_id = cur.fetchone()[0]
                
            session['team_id'] = new_id
            session['username'] = username
            session['is_admin'] = False
            flash('Registration successful! Welcome to the SQL Race.', 'success')
            return redirect(url_for('contest.contests_list'))
        except Exception as e:
            flash(f'Registration failed: {str(e)}', 'danger')
            
    return render_template('register.html')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'team_id' in session:
        return redirect(url_for('contest.contests_list'))
        
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            flash('Please enter both team name and password.', 'danger')
            return render_template('login.html')
            
        with get_main_db() as cur:
            cur.execute("SELECT id, username, password_hash, is_admin FROM teams WHERE username = %s;", (username,))
            user = cur.fetchone()
            
        if user and check_password_hash(user[2], password):
            session['team_id'] = user[0]
            session['username'] = user[1]
            session['is_admin'] = user[3]
            flash(f'Logged in successfully as {username}!', 'success')
            if user[3]:
                return redirect(url_for('admin.admin_dashboard'))
            return redirect(url_for('contest.contests_list'))
        else:
            flash('Invalid team name or password.', 'danger')
            
    return render_template('login.html')

@bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

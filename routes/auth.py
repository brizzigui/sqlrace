from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from translations import translate as _
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from database import get_main_db

bp = Blueprint('auth', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'team_id' not in session:
            flash(_('flash_login_required'), 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'team_id' not in session:
            flash(_('flash_login_first'), 'warning')
            return redirect(url_for('auth.login'))
        if not session.get('is_admin', False):
            flash(_('flash_admin_required'), 'danger')
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
            flash(_('flash_auth_required'), 'danger')
            return render_template('register.html')
            
        hashed_pw = generate_password_hash(password)
        
        try:
            with get_main_db() as cur:
                # Check duplicate
                cur.execute("SELECT id FROM teams WHERE username = %s;", (username,))
                if cur.fetchone():
                    flash(_('flash_username_taken'), 'danger')
                    return render_template('register.html')
                    
                cur.execute("""
                INSERT INTO teams (username, password_hash, is_admin)
                VALUES (%s, %s, FALSE) RETURNING id;
                """, (username, hashed_pw))
                new_id = cur.fetchone()[0]
                
            session['team_id'] = new_id
            session['username'] = username
            session['is_admin'] = False
            flash(_('flash_reg_success'), 'success')
            return redirect(url_for('contest.contests_list'))
        except Exception as e:
            flash(_('flash_reg_failed', error=str(e)), 'danger')
            
    return render_template('register.html')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'team_id' in session:
        return redirect(url_for('contest.contests_list'))
        
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            flash(_('flash_login_missing'), 'danger')
            return render_template('login.html')
            
        with get_main_db() as cur:
            cur.execute("SELECT id, username, password_hash, is_admin FROM teams WHERE username = %s;", (username,))
            user = cur.fetchone()
            
        if user and check_password_hash(user[2], password):
            session['team_id'] = user[0]
            session['username'] = user[1]
            session['is_admin'] = user[3]
            flash(_('flash_login_success', username=username), 'success')
            if user[3]:
                return redirect(url_for('admin.admin_dashboard'))
            return redirect(url_for('contest.contests_list'))
        else:
            flash(_('flash_login_invalid'), 'danger')
            
    return render_template('login.html')

@bp.route('/logout')
def logout():
    session.clear()
    flash(_('flash_logout_info'), 'info')
    return redirect(url_for('auth.login'))

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

from flask import Response
from datetime import datetime
from identicon import generate_identicon_svg

def format_join_duration(created_at):
    if not created_at:
        return _('profile_joined_today'), ""
        
    now = datetime.now()
    delta = now - created_at
    days = delta.days
    date_formatted = created_at.strftime("%B %d, %Y")
    
    if days <= 0:
        duration_str = _('profile_joined_today')
    elif days == 1:
        duration_str = _('profile_joined_1_day_ago')
    elif days < 30:
        duration_str = _('profile_joined_days_ago', days=days)
    elif days < 365:
        months = max(1, days // 30)
        if months == 1:
            duration_str = _('profile_joined_1_month_ago')
        else:
            duration_str = _('profile_joined_months_ago', months=months)
    else:
        years = max(1, days // 365)
        if years == 1:
            duration_str = _('profile_joined_1_year_ago')
        else:
            duration_str = _('profile_joined_years_ago', years=years)
            
    return duration_str, date_formatted

@bp.route('/avatar/<username>.svg')
def team_avatar(username):
    svg = generate_identicon_svg(username, size=120)
    response = Response(svg, mimetype='image/svg+xml')
    response.headers['Cache-Control'] = 'public, max-age=86400'
    return response

@bp.route('/profile')
@login_required
def my_profile():
    return redirect(url_for('auth.team_profile', team_id=session['team_id']))

@bp.route('/team/<int:team_id>')
def team_profile(team_id):
    with get_main_db() as cur:
        cur.execute("SELECT id, username, created_at, is_admin FROM teams WHERE id = %s;", (team_id,))
        team_row = cur.fetchone()
        
        if not team_row:
            flash(_('profile_team_not_found'), 'danger')
            return redirect(url_for('leaderboard.global_leaderboard'))
            
        t_id, username, created_at, is_admin = team_row
        
        cur.execute("SELECT COUNT(*) FROM submissions WHERE team_id = %s;", (team_id,))
        total_submissions = cur.fetchone()[0]
        
        cur.execute("""
            SELECT q.id, q.title, q.difficulty, q.visibility, MIN(s.submitted_at) as solved_at
            FROM questions q
            JOIN submissions s ON q.id = s.question_id
            WHERE s.team_id = %s AND s.status = 'Accepted'
            GROUP BY q.id, q.title, q.difficulty, q.visibility
            ORDER BY solved_at DESC;
        """, (team_id,))
        solved_rows = cur.fetchall()
        
    solved_questions = []
    for q_id, q_title, q_diff, q_vis, solved_at in solved_rows:
        solved_questions.append({
            'id': q_id,
            'title': q_title,
            'difficulty': q_diff,
            'visibility': q_vis,
            'solved_at': solved_at
        })
        
    solved_count = len(solved_questions)
    accuracy_rate = round((solved_count / total_submissions * 100), 1) if total_submissions > 0 else 0.0
    duration_str, date_formatted = format_join_duration(created_at)
    
    team_data = {
        'id': t_id,
        'username': username,
        'created_at': created_at,
        'is_admin': is_admin,
        'joined_duration': duration_str,
        'joined_date': date_formatted,
        'solved_count': solved_count,
        'total_submissions': total_submissions,
        'accuracy_rate': accuracy_rate
    }
    
    return render_template('team_profile.html', team=team_data, solved_questions=solved_questions)


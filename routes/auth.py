from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from translations import translate as _
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from database import get_main_db, log_audit

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

@bp.before_app_request
def enforce_password_change():
    """
    Enforces that any user flagged with must_change_password must update
    their password before accessing any other application resource.
    """
    if session.get('team_id') and session.get('must_change_password'):
        if request.path.startswith('/static/'):
            return None
        allowed_endpoints = {'auth.change_password', 'auth.logout', 'set_lang'}
        if request.endpoint and request.endpoint in allowed_endpoints:
            return None
        return redirect(url_for('auth.change_password'))

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
            log_audit('AUTH', 'TEAM_REGISTER', f"New team registered: {username}", level='INFO', user_id=new_id, username=username, ip_address=request.remote_addr)
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
            cur.execute("SELECT id, username, password_hash, is_admin, COALESCE(must_change_password, FALSE) FROM teams WHERE username = %s;", (username,))
            user = cur.fetchone()
            
        if user and check_password_hash(user[2], password):
            session['team_id'] = user[0]
            session['username'] = user[1]
            session['is_admin'] = user[3]
            session['must_change_password'] = bool(user[4])
            log_audit('AUTH', 'LOGIN_SUCCESS', f"Team '{username}' logged in successfully", level='INFO', user_id=user[0], username=username, ip_address=request.remote_addr)
            flash(_('flash_login_success', username=username), 'success')
            if session['must_change_password']:
                flash(_('flash_must_change_password'), 'warning')
                return redirect(url_for('auth.change_password'))
            if user[3]:
                return redirect(url_for('admin.admin_dashboard'))
            return redirect(url_for('contest.contests_list'))
        else:
            log_audit('AUTH', 'LOGIN_FAILED', f"Failed login attempt for username '{username}'", level='WARNING', username=username, ip_address=request.remote_addr)
            flash(_('flash_login_invalid'), 'danger')
            
    return render_template('login.html')

@bp.route('/logout')
def logout():
    team_id = session.get('team_id')
    username = session.get('username')
    if username:
        log_audit('AUTH', 'LOGOUT', f"Team '{username}' logged out", level='INFO', user_id=team_id, username=username, ip_address=request.remote_addr)
    session.clear()
    flash(_('flash_logout_info'), 'info')
    return redirect(url_for('auth.login'))

@bp.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    team_id = session.get('team_id')
    is_forced = bool(session.get('must_change_password', False))
    
    if request.method == 'POST':
        current_password = request.form.get('current_password', '').strip()
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        with get_main_db() as cur:
            cur.execute("SELECT id, username, password_hash, is_admin, COALESCE(must_change_password, FALSE) FROM teams WHERE id = %s;", (team_id,))
            user = cur.fetchone()
            
        if not user:
            flash(_('flash_login_first'), 'danger')
            return redirect(url_for('auth.login'))
            
        # If not forced, require current password verification
        if not is_forced:
            if not current_password:
                flash(_('flash_auth_required'), 'danger')
                return render_template('change_password.html', is_forced=is_forced)
            if not check_password_hash(user[2], current_password):
                flash(_('flash_current_password_incorrect'), 'danger')
                return render_template('change_password.html', is_forced=is_forced)
                
        if not new_password or not confirm_password:
            flash(_('flash_auth_required'), 'danger')
            return render_template('change_password.html', is_forced=is_forced)
            
        if new_password != confirm_password:
            flash(_('flash_passwords_do_not_match'), 'danger')
            return render_template('change_password.html', is_forced=is_forced)
            
        # Update password and clear must_change_password flag
        hashed_pw = generate_password_hash(new_password)
        with get_main_db() as cur:
            cur.execute("UPDATE teams SET password_hash = %s, must_change_password = FALSE WHERE id = %s;", (hashed_pw, team_id))
            
        session['must_change_password'] = False
        username = user[1]
        log_audit('AUTH', 'PASSWORD_CHANGE', f"Team '{username}' successfully changed their password", level='INFO', user_id=team_id, username=username, ip_address=request.remote_addr)
        flash(_('flash_password_changed_success'), 'success')
        
        if is_forced:
            if user[3]: # is_admin
                return redirect(url_for('admin.admin_dashboard'))
            return redirect(url_for('contest.contests_list'))
        else:
            return redirect(url_for('auth.team_profile', team_id=team_id))
            
    return render_template('change_password.html', is_forced=is_forced)

from flask import Response
from datetime import datetime
from identicon import generate_identicon_svg

def format_join_duration(created_at):
    if not created_at:
        return _('profile_joined_today'), ""
        
    now = datetime.now()
    delta = now - created_at
    days = delta.days
    
    lang = session.get('lang', 'pt')
    if lang == 'pt':
        date_formatted = created_at.strftime("%d/%m/%Y")
    else:
        date_formatted = created_at.strftime("%b %d, %Y")
    
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

import uuid

@bp.route('/avatar/<username>.svg')
def team_avatar(username):
    v_param = request.args.get('v')
    if v_param:
        seed = f"{username}_{v_param}"
    else:
        with get_main_db() as cur:
            cur.execute("SELECT avatar_seed FROM teams WHERE username = %s;", (username,))
            row = cur.fetchone()
            seed = f"{username}_{row[0]}" if (row and row[0]) else username
            
    svg = generate_identicon_svg(seed, size=120)
    response = Response(svg, mimetype='image/svg+xml')
    response.headers['Cache-Control'] = 'no-cache, max-age=0' if v_param else 'public, max-age=86400'
    return response

@bp.route('/profile')
@login_required
def my_profile():
    return redirect(url_for('auth.team_profile', team_id=session['team_id']))

@bp.route('/profile/regen_avatar', methods=['POST'])
@login_required
def regen_avatar():
    team_id = session.get('team_id')
    new_seed = uuid.uuid4().hex[:12]
    with get_main_db() as cur:
        cur.execute("UPDATE teams SET avatar_seed = %s WHERE id = %s;", (new_seed, team_id))
    flash(_('profile_avatar_regenerated'), 'success')
    return redirect(url_for('auth.team_profile', team_id=team_id))

@bp.route('/team/<int:team_id>')
def team_profile(team_id):
    with get_main_db() as cur:
        cur.execute("SELECT id, username, created_at, is_admin, avatar_seed FROM teams WHERE id = %s;", (team_id,))
        team_row = cur.fetchone()
        
        if not team_row:
            flash(_('profile_team_not_found'), 'danger')
            return redirect(url_for('leaderboard.global_leaderboard'))
            
        t_id, username, created_at, is_admin, avatar_seed = team_row
        
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
    total_score = sum(q['difficulty'] for q in solved_questions)
    duration_str, date_formatted = format_join_duration(created_at)
    
    team_data = {
        'id': t_id,
        'username': username,
        'created_at': created_at,
        'is_admin': is_admin,
        'avatar_seed': avatar_seed or '',
        'joined_duration': duration_str,
        'joined_date': date_formatted,
        'solved_count': solved_count,
        'total_submissions': total_submissions,
        'total_score': total_score
    }
    
    return render_template('team_profile.html', team=team_data, solved_questions=solved_questions)



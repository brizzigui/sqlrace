import os
import shutil
import math
import subprocess
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from translations import translate as _
from werkzeug.utils import secure_filename
from routes.auth import admin_required
from database import get_main_db, log_audit, main_pool, sandbox_pool
from datetime import datetime

bp = Blueprint('admin', __name__)

UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def format_bytes(size):
    if size == 0:
        return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size, 1024)))
    p = math.pow(1024, i)
    s = round(size / p, 2)
    return f"{s} {size_name[i]}"

@bp.route('/admin')
@admin_required
def admin_dashboard():
    with get_main_db() as cur:
        # Get stats
        cur.execute("SELECT COUNT(*) FROM teams WHERE is_admin = FALSE;")
        team_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM submissions;")
        submission_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM questions;")
        question_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM audit_logs WHERE timestamp >= NOW() - INTERVAL '7 days';")
        log_count = cur.fetchone()[0]

    # Calculate storage stats summary for dashboard card
    total_storage_bytes = 0
    if os.path.exists(UPLOAD_FOLDER):
        for f in os.listdir(UPLOAD_FOLDER):
            fp = os.path.join(UPLOAD_FOLDER, f)
            if os.path.isfile(fp):
                total_storage_bytes += os.path.getsize(fp)
                
    return render_template(
        'admin_dashboard.html', 
        team_count=team_count,
        submission_count=submission_count,
        question_count=question_count,
        log_count=log_count,
        storage_size_formatted=format_bytes(total_storage_bytes)
    )

@bp.route('/admin/contests')
@admin_required
def admin_contests():
    with get_main_db() as cur:
        # Get contests
        cur.execute("SELECT id, title, description, start_time, end_time FROM contests ORDER BY start_time DESC;")
        contests = cur.fetchall()
        
        # Get questions
        cur.execute("SELECT id, title, difficulty, visibility FROM questions ORDER BY id DESC;")
        questions = cur.fetchall()
        
    return render_template('admin_contests.html', contests=contests, questions=questions)

@bp.route('/admin/questions')
@admin_required
def admin_questions():
    with get_main_db() as cur:
        # Get questions with their associated contests and difficulty
        cur.execute("""
            SELECT q.id, q.title, q.visibility, q.difficulty,
                   COALESCE(string_agg(c.title, ', '), 'None') as contests_list
            FROM questions q
            LEFT JOIN contest_questions cq ON q.id = cq.question_id
            LEFT JOIN contests c ON cq.contest_id = c.id
            GROUP BY q.id, q.title, q.visibility, q.difficulty
            ORDER BY q.id DESC;
        """)
        questions = cur.fetchall()
        
    return render_template('admin_questions.html', questions=questions)

@bp.route('/admin/teams')
@admin_required
def admin_teams():
    with get_main_db() as cur:
        # Get all registered teams
        cur.execute("SELECT id, username, created_at, is_admin FROM teams ORDER BY id ASC;")
        teams = cur.fetchall()
        
    return render_template('admin_teams.html', teams=teams)

@bp.route('/admin/contest/create', methods=['POST'])
@admin_required
def create_contest():
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    start_time_raw = request.form.get('start_time', '').strip()
    end_time_raw = request.form.get('end_time', '').strip()
    question_ids = request.form.getlist('question_ids')
    
    if not title or not start_time_raw or not end_time_raw:
        flash(_('flash_contest_fields_required'), 'danger')
        return redirect(url_for('admin.admin_contests'))
        
    try:
        start_time = datetime.fromisoformat(start_time_raw)
        end_time = datetime.fromisoformat(end_time_raw)
        
        if end_time <= start_time:
            flash(_('flash_contest_end_after_start'), 'danger')
            return redirect(url_for('admin.admin_contests'))
            
        with get_main_db() as cur:
            cur.execute("""
                INSERT INTO contests (title, description, start_time, end_time)
                VALUES (%s, %s, %s, %s) RETURNING id;
            """, (title, description, start_time, end_time))
            contest_id = cur.fetchone()[0]
            
            # Associate selected questions
            for q_id in question_ids:
                cur.execute("""
                    INSERT INTO contest_questions (contest_id, question_id)
                    VALUES (%s, %s);
                """, (contest_id, int(q_id)))
            
        log_audit('CONTEST', 'CREATE_CONTEST', f"Created contest '{title}' (ID: {contest_id})", level='INFO', user_id=session.get('team_id'), username=session.get('username'), ip_address=request.remote_addr)
        flash(_('flash_contest_created', title=title), "success")
    except Exception as e:
        flash(_('flash_contest_create_failed', error=str(e)), "danger")
        
    return redirect(url_for('admin.admin_contests'))

@bp.route('/admin/contest/edit/<int:contest_id>', methods=['GET', 'POST'])
@admin_required
def edit_contest(contest_id):
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        start_time_raw = request.form.get('start_time', '').strip()
        end_time_raw = request.form.get('end_time', '').strip()
        question_ids = request.form.getlist('question_ids')
        
        if not title or not start_time_raw or not end_time_raw:
            flash(_('flash_contest_fields_required'), 'danger')
            return redirect(url_for('admin.edit_contest', contest_id=contest_id))
            
        try:
            start_time = datetime.fromisoformat(start_time_raw)
            end_time = datetime.fromisoformat(end_time_raw)
            
            if end_time <= start_time:
                flash(_('flash_contest_end_after_start'), 'danger')
                return redirect(url_for('admin.edit_contest', contest_id=contest_id))
                
            with get_main_db() as cur:
                cur.execute("""
                    UPDATE contests 
                    SET title = %s, description = %s, start_time = %s, end_time = %s
                    WHERE id = %s;
                """, (title, description, start_time, end_time, contest_id))
                
                # Update questions association
                cur.execute("DELETE FROM contest_questions WHERE contest_id = %s;", (contest_id,))
                for q_id in question_ids:
                    cur.execute("""
                        INSERT INTO contest_questions (contest_id, question_id)
                        VALUES (%s, %s);
                    """, (contest_id, int(q_id)))
                    
            log_audit('CONTEST', 'EDIT_CONTEST', f"Updated contest '{title}' (ID: {contest_id})", level='INFO', user_id=session.get('team_id'), username=session.get('username'), ip_address=request.remote_addr)
            flash(_('flash_contest_updated', title=title), "success")
            return redirect(url_for('admin.admin_contests'))
        except Exception as e:
            flash(_('flash_contest_update_failed', error=str(e)), "danger")
            return redirect(url_for('admin.edit_contest', contest_id=contest_id))
            
    # GET request
    with get_main_db() as cur:
        cur.execute("SELECT id, title, description, start_time, end_time FROM contests WHERE id = %s;", (contest_id,))
        contest = cur.fetchone()
        if not contest:
            flash(_('flash_contest_not_found'), "danger")
            return redirect(url_for('admin.admin_contests'))
            
        # Get all questions with difficulty and visibility
        cur.execute("SELECT id, title, difficulty, visibility FROM questions ORDER BY id DESC;")
        all_questions = cur.fetchall()
        
        # Get associated question IDs
        cur.execute("SELECT question_id FROM contest_questions WHERE contest_id = %s;", (contest_id,))
        associated_ids = {row[0] for row in cur.fetchall()}
        
    contest_data = {
        'id': contest[0],
        'title': contest[1],
        'description': contest[2],
        'start_time': contest[3].strftime('%Y-%m-%dT%H:%M'),
        'end_time': contest[4].strftime('%Y-%m-%dT%H:%M')
    }
    
    return render_template(
        'admin_edit_contest.html',
        contest=contest_data,
        questions=all_questions,
        associated_ids=associated_ids
    )

@bp.route('/admin/question/create', methods=['POST'])
@admin_required
def create_question():
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    init_sql = request.form.get('init_sql', '').strip()
    solution_sql = request.form.get('solution_sql', '').strip()
    visibility = request.form.get('visibility', 'public').strip()
    try:
        difficulty = int(request.form.get('difficulty', 1))
        if not (1 <= difficulty <= 5):
            difficulty = 1
    except ValueError:
        difficulty = 1
    
    if not title or not description or not init_sql or not solution_sql:
        flash(_('flash_question_fields_required'), 'danger')
        return redirect(url_for('admin.admin_questions'))
        
    try:
        with get_main_db() as cur:
            cur.execute("""
                INSERT INTO questions (title, description, init_sql, solution_sql, visibility, difficulty)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id;
            """, (title, description, init_sql, solution_sql, visibility, difficulty))
            q_id = cur.fetchone()[0]
            
        log_audit('QUESTION', 'CREATE_QUESTION', f"Created question '{title}' (ID: {q_id})", level='INFO', user_id=session.get('team_id'), username=session.get('username'), ip_address=request.remote_addr)
        flash(_('flash_question_created', title=title), "success")
    except Exception as e:
        flash(_('flash_question_create_failed', error=str(e)), "danger")
        
    return redirect(url_for('admin.admin_questions'))

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'}

@bp.route('/admin/upload_image', methods=['POST'])
@admin_required
def upload_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    # Extension check
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({'error': _('js_invalid_image_type')}), 400
    
    # 10MB Size check
    file.seek(0, os.SEEK_END)
    file_length = file.tell()
    file.seek(0)
    if file_length > MAX_FILE_SIZE:
        return jsonify({'error': _('js_file_too_large')}), 400

    if file:
        # Canonical filename generation: img_YYYYMMDD_HHMMSS_<uuid8>.<ext>
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = uuid.uuid4().hex[:8]
        filename = f"img_{timestamp}_{unique_id}{ext}"
        
        # Ensure uploads folder exists
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        log_audit('STORAGE', 'IMAGE_UPLOAD', f"Uploaded file: {filename}", level='INFO', user_id=session.get('team_id'), username=session.get('username'), ip_address=request.remote_addr)
        url = url_for('static', filename=f"uploads/{filename}")
        return jsonify({'url': url, 'filename': filename})
    return jsonify({'error': 'Failed to save file'}), 500

@bp.route('/admin/contest/delete/<int:contest_id>', methods=['POST'])
@admin_required
def delete_contest(contest_id):
    try:
        with get_main_db() as cur:
            cur.execute("DELETE FROM contests WHERE id = %s;", (contest_id,))
        log_audit('CONTEST', 'DELETE_CONTEST', f"Deleted contest ID {contest_id}", level='WARNING', user_id=session.get('team_id'), username=session.get('username'), ip_address=request.remote_addr)
        flash(_('flash_contest_deleted'), "warning")
    except Exception as e:
        flash(_('flash_contest_delete_failed', error=str(e)), "danger")
    return redirect(url_for('admin.admin_contests'))

@bp.route('/admin/question/delete/<int:question_id>', methods=['POST'])
@admin_required
def delete_question(question_id):
    try:
        with get_main_db() as cur:
            cur.execute("DELETE FROM questions WHERE id = %s;", (question_id,))
        log_audit('QUESTION', 'DELETE_QUESTION', f"Deleted question ID {question_id}", level='WARNING', user_id=session.get('team_id'), username=session.get('username'), ip_address=request.remote_addr)
        flash(_('flash_question_deleted'), "warning")
    except Exception as e:
        flash(_('flash_question_delete_failed', error=str(e)), "danger")
    return redirect(url_for('admin.admin_questions'))

@bp.route('/admin/question/clear_solutions/<int:question_id>', methods=['POST'])
@admin_required
def clear_question_solutions(question_id):
    try:
        with get_main_db() as cur:
            cur.execute("SELECT title FROM questions WHERE id = %s;", (question_id,))
            q = cur.fetchone()
            if not q:
                flash(_('error_question_not_found'), "danger")
                return redirect(url_for('admin.admin_questions'))
            q_title = q[0]
            
            cur.execute("DELETE FROM submissions WHERE question_id = %s;", (question_id,))
            deleted_count = cur.rowcount
            
        log_audit('QUESTION', 'CLEAR_SOLUTIONS', f"Cleared {deleted_count} user solution(s) for question '{q_title}' (ID: {question_id})", level='WARNING', user_id=session.get('team_id'), username=session.get('username'), ip_address=request.remote_addr)
        flash(_('flash_question_solutions_cleared', title=q_title), "warning")
    except Exception as e:
        flash(_('flash_question_solutions_clear_failed', error=str(e)), "danger")
    
    redirect_url = request.referrer or url_for('admin.admin_questions')
    return redirect(redirect_url)

@bp.route('/admin/question/edit/<int:question_id>', methods=['GET'])
@admin_required
def edit_question_view(question_id):
    with get_main_db() as cur:
        cur.execute("""
            SELECT id, title, description, init_sql, solution_sql, visibility, difficulty 
            FROM questions WHERE id = %s;
        """, (question_id,))
        question = cur.fetchone()
        if not question:
            flash(_('error_question_not_found'), "danger")
            return redirect(url_for('admin.admin_questions'))
            
    q_data = {
        'id': question[0],
        'title': question[1],
        'description': question[2],
        'init_sql': question[3],
        'solution_sql': question[4],
        'visibility': question[5],
        'difficulty': question[6]
    }
    return render_template('admin_edit_question.html', question=q_data)

@bp.route('/admin/question/edit/<int:question_id>', methods=['POST'])
@admin_required
def edit_question(question_id):
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    init_sql = request.form.get('init_sql', '').strip()
    solution_sql = request.form.get('solution_sql', '').strip()
    visibility = request.form.get('visibility', 'public').strip()
    try:
        difficulty = int(request.form.get('difficulty', 1))
        if not (1 <= difficulty <= 5):
            difficulty = 1
    except ValueError:
        difficulty = 1
        
    if not title or not description or not init_sql or not solution_sql:
        flash(_('flash_admin_fields_required'), "danger")
        return redirect(url_for('admin.edit_question_view', question_id=question_id))
        
    try:
        with get_main_db() as cur:
            cur.execute("""
                UPDATE questions 
                SET title = %s, description = %s, init_sql = %s, solution_sql = %s, visibility = %s, difficulty = %s 
                WHERE id = %s;
            """, (title, description, init_sql, solution_sql, visibility, difficulty, question_id))
        log_audit('QUESTION', 'EDIT_QUESTION', f"Updated question '{title}' (ID: {question_id})", level='INFO', user_id=session.get('team_id'), username=session.get('username'), ip_address=request.remote_addr)
        flash(_('flash_question_updated', title=title), "success")
    except Exception as e:
        flash(_('flash_question_update_failed', error=str(e)), "danger")
        
    return redirect(url_for('admin.admin_questions'))

@bp.route('/admin/team/update_role/<int:team_id>', methods=['POST'])
@admin_required
def update_team_role(team_id):
    if team_id == session.get('team_id'):
        flash(_('flash_team_role_own'), "danger")
        return redirect(url_for('admin.admin_teams'))
        
    is_admin_str = request.form.get('is_admin', 'false').lower()
    is_admin = is_admin_str == 'true'
    
    try:
        with get_main_db() as cur:
            cur.execute("UPDATE teams SET is_admin = %s WHERE id = %s;", (is_admin, team_id))
        log_audit('TEAM', 'ROLE_UPDATE', f"Updated team ID {team_id} admin status to {is_admin}", level='WARNING', user_id=session.get('team_id'), username=session.get('username'), ip_address=request.remote_addr)
        flash(_('flash_team_role_updated'), "success")
    except Exception as e:
        flash(_('flash_team_role_update_failed', error=str(e)), "danger")
        
    return redirect(url_for('admin.admin_teams'))

@bp.route('/admin/team/delete/<int:team_id>', methods=['POST'])
@admin_required
def delete_team(team_id):
    if team_id == session.get('team_id'):
        flash(_('flash_team_delete_own'), "danger")
        return redirect(url_for('admin.admin_teams'))
        
    try:
        with get_main_db() as cur:
            cur.execute("DELETE FROM teams WHERE id = %s;", (team_id,))
        log_audit('TEAM', 'DELETE_TEAM', f"Deleted team ID {team_id}", level='WARNING', user_id=session.get('team_id'), username=session.get('username'), ip_address=request.remote_addr)
        flash(_('flash_team_deleted'), "warning")
    except Exception as e:
        flash(_('flash_team_delete_failed', error=str(e)), "danger")
        
    return redirect(url_for('admin.admin_teams'))

# ==========================================
# Manage Storage Routes
# ==========================================
@bp.route('/admin/storage')
@admin_required
def admin_storage():
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    with get_main_db() as cur:
        cur.execute("SELECT id, title, description, init_sql, solution_sql FROM questions;")
        questions = cur.fetchall()
        
    files_list = []
    total_size_bytes = 0
    unused_count = 0
    unused_size_bytes = 0
    
    if os.path.exists(UPLOAD_FOLDER):
        for fname in os.listdir(UPLOAD_FOLDER):
            fpath = os.path.join(UPLOAD_FOLDER, fname)
            if os.path.isfile(fpath):
                fsize = os.path.getsize(fpath)
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                total_size_bytes += fsize
                
                # Check question references
                used_in = []
                for q in questions:
                    q_id, q_title, q_desc, q_init, q_sol = q
                    if fname in (q_desc or '') or fname in (q_init or '') or fname in (q_sol or ''):
                        used_in.append({'id': q_id, 'title': q_title})
                        
                is_used = len(used_in) > 0
                if not is_used:
                    unused_count += 1
                    unused_size_bytes += fsize
                    
                files_list.append({
                    'filename': fname,
                    'path': f"/static/uploads/{fname}",
                    'size_bytes': fsize,
                    'size_formatted': format_bytes(fsize),
                    'mtime': mtime.strftime('%Y-%m-%d %H:%M:%S'),
                    'used_in': used_in,
                    'is_used': is_used
                })
                
    files_list.sort(key=lambda x: x['mtime'], reverse=True)
    
    disk_total, disk_used, disk_free = shutil.disk_usage('.')
    others_bytes = max(0, disk_used - total_size_bytes)
    
    storage_stats = {
        'total_files': len(files_list),
        'total_size_bytes': total_size_bytes,
        'total_size_formatted': format_bytes(total_size_bytes),
        'unused_files_count': unused_count,
        'unused_size_bytes': unused_size_bytes,
        'unused_size_formatted': format_bytes(unused_size_bytes),
        'disk_total_bytes': disk_total,
        'disk_total_formatted': format_bytes(disk_total),
        'disk_free_bytes': disk_free,
        'disk_free_formatted': format_bytes(disk_free),
        'others_bytes': others_bytes,
        'others_formatted': format_bytes(others_bytes),
        'uploads_pct': round((total_size_bytes / disk_total * 100), 2) if disk_total else 0,
        'others_pct': round((others_bytes / disk_total * 100), 2) if disk_total else 0,
        'free_pct': round((disk_free / disk_total * 100), 2) if disk_total else 0,
        'disk_used_percent': round((disk_used / disk_total) * 100, 1) if disk_total else 0
    }
    
    return render_template('admin_storage.html', files=files_list, stats=storage_stats)

@bp.route('/admin/storage/delete', methods=['POST'])
@admin_required
def delete_storage_file():
    filename = request.form.get('filename', '').strip()
    if not filename:
        flash(_('flash_file_name_required'), 'danger')
        return redirect(url_for('admin.admin_storage'))
        
    safe_fname = secure_filename(filename)
    filepath = os.path.join(UPLOAD_FOLDER, safe_fname)
    
    abs_upload = os.path.abspath(UPLOAD_FOLDER)
    abs_file = os.path.abspath(filepath)
    
    if not abs_file.startswith(abs_upload):
        flash(_('flash_file_invalid'), 'danger')
        return redirect(url_for('admin.admin_storage'))
        
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            log_audit('STORAGE', 'FILE_DELETE', f"Deleted uploaded file '{safe_fname}'", level='WARNING', user_id=session.get('team_id'), username=session.get('username'), ip_address=request.remote_addr)
            flash(_('flash_file_deleted_success', filename=safe_fname), 'success')
        except Exception as e:
            flash(_('flash_file_delete_failed', error=str(e)), 'danger')
    else:
        flash(_('flash_file_not_found'), 'danger')
        
    return redirect(url_for('admin.admin_storage'))

@bp.route('/admin/storage/delete_unused', methods=['POST'])
@admin_required
def delete_unused_storage_files():
    with get_main_db() as cur:
        cur.execute("SELECT description, init_sql, solution_sql FROM questions;")
        questions = cur.fetchall()
        
    all_q_text = " ".join([(q[0] or '') + " " + (q[1] or '') + " " + (q[2] or '') for q in questions])
    
    deleted_count = 0
    freed_bytes = 0
    
    if os.path.exists(UPLOAD_FOLDER):
        for fname in os.listdir(UPLOAD_FOLDER):
            filepath = os.path.join(UPLOAD_FOLDER, fname)
            if os.path.isfile(filepath):
                if fname not in all_q_text:
                    try:
                        fsize = os.path.getsize(filepath)
                        os.remove(filepath)
                        deleted_count += 1
                        freed_bytes += fsize
                    except Exception:
                        pass
                        
    if deleted_count > 0:
        freed_fmt = format_bytes(freed_bytes)
        log_audit('STORAGE', 'FILE_BULK_DELETE', f"Deleted {deleted_count} unused files, freeing {freed_fmt}", level='WARNING', user_id=session.get('team_id'), username=session.get('username'), ip_address=request.remote_addr)
        flash(_('flash_unused_files_deleted', count=deleted_count, size=freed_fmt), 'success')
    else:
        flash(_('flash_no_unused_files'), 'info')
        
    return redirect(url_for('admin.admin_storage'))

# ==========================================
# Manage Resources Routes
# ==========================================
def get_system_resources_data():
    # 1. Docker Containers Status
    containers = []
    try:
        res = subprocess.run(
            'docker ps -a --format "{{.ID}}|{{.Names}}|{{.Status}}|{{.Image}}"',
            shell=True, capture_output=True, text=True, timeout=3
        )
        if res.returncode == 0 and res.stdout.strip():
            lines = res.stdout.strip().split('\n')
            for line in lines:
                parts = line.split('|')
                if len(parts) >= 4:
                    c_id, c_name, c_status, c_image = parts[0], parts[1], parts[2], parts[3]
                    is_running = 'up' in c_status.lower()
                    containers.append({
                        'id': c_id[:12],
                        'name': c_name,
                        'status': c_status,
                        'image': c_image,
                        'is_running': is_running
                    })
    except Exception:
        pass

    # 2. Database Services and Storage Stats
    db_metrics = {
        'main_db_size': 'N/A',
        'sandbox_db_size': 'N/A',
        'main_active_queries': 0,
        'sandbox_active_queries': 0
    }
    try:
        with get_main_db() as cur:
            cur.execute("SELECT pg_size_pretty(pg_database_size(current_database()));")
            db_metrics['main_db_size'] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM pg_stat_activity WHERE state = 'active';")
            db_metrics['main_active_queries'] = cur.fetchone()[0]
    except Exception:
        pass

    try:
        from database import get_sandbox_db
        with get_sandbox_db() as cur:
            cur.execute("SELECT pg_size_pretty(pg_database_size(current_database()));")
            db_metrics['sandbox_db_size'] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM pg_stat_activity WHERE state = 'active';")
            db_metrics['sandbox_active_queries'] = cur.fetchone()[0]
    except Exception:
        pass

    # 3. Connection Pools Status
    main_pool_stats = {'active': 0, 'max': 20}
    sandbox_pool_stats = {'active': 0, 'max': 20}
    if main_pool:
        main_pool_stats['active'] = len(main_pool._used) if hasattr(main_pool, '_used') else 0
        main_pool_stats['max'] = main_pool.maxconn if hasattr(main_pool, 'maxconn') else 20
    if sandbox_pool:
        sandbox_pool_stats['active'] = len(sandbox_pool._used) if hasattr(sandbox_pool, '_used') else 0
        sandbox_pool_stats['max'] = sandbox_pool.maxconn if hasattr(sandbox_pool, 'maxconn') else 20

    # 4. Judge Performance & Evaluation Metrics
    with get_main_db() as cur:
        cur.execute("""
            SELECT 
                COUNT(*) as total_subs,
                COALESCE(AVG(execution_time_ms), 0) as avg_exec_time,
                COALESCE(MAX(execution_time_ms), 0) as max_exec_time,
                COALESCE(AVG(wait_time_ms), 0) as avg_wait_time,
                SUM(CASE WHEN submitted_at >= NOW() - INTERVAL '24 hours' THEN 1 ELSE 0 END) as subs_24h,
                SUM(CASE WHEN status = 'Accepted' THEN 1 ELSE 0 END) as accepted_subs,
                SUM(CASE WHEN status = 'Wrong Answer' THEN 1 ELSE 0 END) as wa_subs,
                SUM(CASE WHEN status = 'Runtime Error' THEN 1 ELSE 0 END) as re_subs
            FROM submissions;
        """)
        row = cur.fetchone()
        
    total_subs = row[0] or 0
    avg_exec_time = round(float(row[1] or 0), 1)
    max_exec_time = round(float(row[2] or 0), 1)
    avg_wait_time = round(float(row[3] or 0), 1)
    subs_24h = row[4] or 0
    accepted_subs = row[5] or 0
    wa_subs = row[6] or 0
    re_subs = row[7] or 0
    acceptance_rate = round((accepted_subs / total_subs * 100), 1) if total_subs > 0 else 0

    # 5. System Load & RAM Utilization (Linux/Cross-platform)
    sys_metrics = {
        'cpu_percent': 0,
        'ram_percent': 0,
        'ram_used_formatted': 'N/A',
        'ram_total_formatted': 'N/A',
        'load_1m': 0,
        'cpu_cores': os.cpu_count() or 1
    }

    try:
        import psutil
        sys_metrics['cpu_percent'] = round(psutil.cpu_percent(interval=None), 1)
        mem = psutil.virtual_memory()
        sys_metrics['ram_percent'] = round(mem.percent, 1)
        sys_metrics['ram_used_formatted'] = format_bytes(mem.used)
        sys_metrics['ram_total_formatted'] = format_bytes(mem.total)
    except Exception:
        try:
            with open('/proc/meminfo', 'r') as f:
                mem = {}
                for line in f:
                    parts = line.split(':')
                    if len(parts) == 2:
                        k = parts[0].strip()
                        v = parts[1].strip().split()[0]
                        mem[k] = int(v) * 1024
                total = mem.get('MemTotal', 0)
                available = mem.get('MemAvailable', mem.get('MemFree', 0))
                used = total - available
                if total > 0:
                    sys_metrics['ram_percent'] = round((used / total) * 100, 1)
                    sys_metrics['ram_used_formatted'] = format_bytes(used)
                    sys_metrics['ram_total_formatted'] = format_bytes(total)
        except Exception:
            pass

    if hasattr(os, 'getloadavg'):
        try:
            load = os.getloadavg()
            sys_metrics['load_1m'] = round(load[0], 2)
            if sys_metrics['cpu_percent'] == 0:
                sys_metrics['cpu_percent'] = min(100.0, round((load[0] / sys_metrics['cpu_cores']) * 100, 1))
        except Exception:
            pass

    return {
        'containers': containers,
        'db_metrics': db_metrics,
        'main_pool': main_pool_stats,
        'sandbox_pool': sandbox_pool_stats,
        'judge_metrics': {
            'total_subs': total_subs,
            'avg_exec_time_ms': avg_exec_time,
            'max_exec_time_ms': max_exec_time,
            'avg_wait_time_ms': avg_wait_time,
            'subs_24h': subs_24h,
            'accepted_subs': accepted_subs,
            'wa_subs': wa_subs,
            're_subs': re_subs,
            'acceptance_rate': acceptance_rate
        },
        'system': sys_metrics
    }

@bp.route('/admin/resources')
@admin_required
def admin_resources():
    resource_data = get_system_resources_data()
    return render_template('admin_resources.html', resources=resource_data)

@bp.route('/admin/api/resources')
@admin_required
def api_resources():
    resource_data = get_system_resources_data()
    return jsonify(resource_data)

# ==========================================
# Manage Logs Routes
# ==========================================
@bp.route('/admin/logs')
@admin_required
def admin_logs():
    category = request.args.get('category', '').strip()
    level = request.args.get('level', '').strip()
    search = request.args.get('search', '').strip()
    try:
        page = max(1, int(request.args.get('page', 1)))
    except ValueError:
        page = 1
        
    per_page = 50
    offset = (page - 1) * per_page
    
    where_clauses = ["timestamp >= NOW() - INTERVAL '7 days'"]
    params = []
    
    if category and category != 'ALL':
        where_clauses.append("category = %s")
        params.append(category)
        
    if level and level != 'ALL':
        where_clauses.append("level = %s")
        params.append(level)
        
    if search:
        where_clauses.append("(message ILIKE %s OR action ILIKE %s OR username ILIKE %s OR ip_address ILIKE %s)")
        search_pattern = f"%{search}%"
        params.extend([search_pattern, search_pattern, search_pattern, search_pattern])
        
    where_sql = " WHERE " + " AND ".join(where_clauses)
    
    with get_main_db() as cur:
        cur.execute("DELETE FROM audit_logs WHERE timestamp < NOW() - INTERVAL '7 days';")
        
        cur.execute(f"SELECT COUNT(*) FROM audit_logs {where_sql};", tuple(params))
        total_logs = cur.fetchone()[0]
        
        cur.execute(f"""
            SELECT id, timestamp, level, category, action, message, user_id, username, ip_address
            FROM audit_logs
            {where_sql}
            ORDER BY id DESC
            LIMIT %s OFFSET %s;
        """, tuple(params + [per_page, offset]))
        logs_rows = cur.fetchall()
        
    logs = []
    for r in logs_rows:
        logs.append({
            'id': r[0],
            'timestamp': r[1].strftime('%Y-%m-%d %H:%M:%S'),
            'level': r[2],
            'category': r[3],
            'action': r[4],
            'message': r[5],
            'user_id': r[6],
            'username': r[7] or 'System',
            'ip_address': r[8] or '-'
        })
        
    total_pages = math.ceil(total_logs / per_page) if total_logs > 0 else 1
    
    return render_template(
        'admin_logs.html',
        logs=logs,
        total_logs=total_logs,
        page=page,
        total_pages=total_pages,
        category=category,
        level=level,
        search=search
    )

@bp.route('/admin/logs/clear', methods=['POST'])
@admin_required
def clear_admin_logs():
    try:
        with get_main_db() as cur:
            cur.execute("DELETE FROM audit_logs;")
        log_audit('SYSTEM', 'LOGS_CLEARED', "All audit logs were cleared by admin", level='CRITICAL', user_id=session.get('team_id'), username=session.get('username'), ip_address=request.remote_addr)
        flash(_('flash_logs_cleared'), 'warning')
    except Exception as e:
        flash(_('flash_logs_clear_failed', error=str(e)), 'danger')
        
    return redirect(url_for('admin.admin_logs'))



import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from translations import translate as _
from werkzeug.utils import secure_filename
from routes.auth import admin_required
from database import get_main_db
from datetime import datetime

bp = Blueprint('admin', __name__)

UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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
        
    return render_template(
        'admin_dashboard.html', 
        team_count=team_count,
        submission_count=submission_count,
        question_count=question_count
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
                VALUES (%s, %s, %s, %s, %s, %s);
            """, (title, description, init_sql, solution_sql, visibility, difficulty))
            
        flash(_('flash_question_created', title=title), "success")
    except Exception as e:
        flash(_('flash_question_create_failed', error=str(e)), "danger")
        
    return redirect(url_for('admin.admin_questions'))

@bp.route('/admin/upload_image', methods=['POST'])
@admin_required
def upload_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file:
        filename = secure_filename(file.filename)
        # Unique filename using timestamp
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f"{timestamp}_{filename}"
        
        # Ensure uploads folder exists
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        url = url_for('static', filename=f"uploads/{filename}")
        return jsonify({'url': url})
    return jsonify({'error': 'Failed to save file'}), 500

@bp.route('/admin/contest/delete/<int:contest_id>', methods=['POST'])
@admin_required
def delete_contest(contest_id):
    try:
        with get_main_db() as cur:
            cur.execute("DELETE FROM contests WHERE id = %s;", (contest_id,))
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
        flash(_('flash_question_deleted'), "warning")
    except Exception as e:
        flash(_('flash_question_delete_failed', error=str(e)), "danger")
    return redirect(url_for('admin.admin_questions'))

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
        flash(_('flash_team_deleted'), "warning")
    except Exception as e:
        flash(_('flash_team_delete_failed', error=str(e)), "danger")
        
    return redirect(url_for('admin.admin_teams'))


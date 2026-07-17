from flask import Blueprint, render_template, request, redirect, url_for, flash
from routes.auth import admin_required
from database import get_main_db
from datetime import datetime

bp = Blueprint('admin', __name__)

@bp.route('/admin')
@admin_required
def admin_dashboard():
    with get_main_db() as cur:
        # Get contests
        cur.execute("SELECT id, title, description, start_time, end_time FROM contests ORDER BY start_time DESC;")
        contests = cur.fetchall()
        
        # Get questions grouped by contest
        cur.execute("""
            SELECT q.id, q.title, q.contest_id, c.title as contest_title 
            FROM questions q 
            JOIN contests c ON q.contest_id = c.id 
            ORDER BY q.contest_id, q.id;
        """)
        questions = cur.fetchall()
        
        # Get stats
        cur.execute("SELECT COUNT(*) FROM teams WHERE is_admin = FALSE;")
        team_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM submissions;")
        submission_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM questions;")
        question_count = cur.fetchone()[0]
        
    return render_template(
        'admin_dashboard.html', 
        contests=contests, 
        questions=questions, 
        team_count=team_count,
        submission_count=submission_count,
        question_count=question_count
    )

@bp.route('/admin/contest/create', methods=['POST'])
@admin_required
def create_contest():
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    start_time_raw = request.form.get('start_time', '').strip()
    end_time_raw = request.form.get('end_time', '').strip()
    
    if not title or not start_time_raw or not end_time_raw:
        flash('Contest title, start time, and end time are required.', 'danger')
        return redirect(url_for('admin.admin_dashboard'))
        
    try:
        # HTML5 datetime-local outputs format 'YYYY-MM-DDTHH:MM' or with seconds
        # psycopg2 can handle strings directly, but parsing validates correctness
        start_time = datetime.fromisoformat(start_time_raw)
        end_time = datetime.fromisoformat(end_time_raw)
        
        if end_time <= start_time:
            flash('End time must be after start time.', 'danger')
            return redirect(url_for('admin.admin_dashboard'))
            
        with get_main_db() as cur:
            cur.execute("""
                INSERT INTO contests (title, description, start_time, end_time)
                VALUES (%s, %s, %s, %s);
            """, (title, description, start_time, end_time))
            
        flash(f"Contest '{title}' created successfully!", "success")
    except Exception as e:
        flash(f"Failed to create contest: {str(e)}", "danger")
        
    return redirect(url_for('admin.admin_dashboard'))

@bp.route('/admin/question/create', methods=['POST'])
@admin_required
def create_question():
    contest_id = request.form.get('contest_id')
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    init_sql = request.form.get('init_sql', '').strip()
    solution_sql = request.form.get('solution_sql', '').strip()
    if not contest_id or not title or not description or not init_sql or not solution_sql:
        flash('All question fields are required.', 'danger')
        return redirect(url_for('admin.admin_dashboard'))
        
    try:
        with get_main_db() as cur:
            cur.execute("""
                INSERT INTO questions (contest_id, title, description, init_sql, solution_sql)
                VALUES (%s, %s, %s, %s, %s);
            """, (contest_id, title, description, init_sql, solution_sql))
            
        flash(f"Question '{title}' created successfully!", "success")
    except Exception as e:
        flash(f"Failed to create question: {str(e)}", "danger")
        
    return redirect(url_for('admin.admin_dashboard'))

@bp.route('/admin/contest/delete/<int:contest_id>', methods=['POST'])
@admin_required
def delete_contest(contest_id):
    try:
        with get_main_db() as cur:
            cur.execute("DELETE FROM contests WHERE id = %s;", (contest_id,))
        flash("Contest deleted successfully.", "warning")
    except Exception as e:
        flash(f"Failed to delete contest: {str(e)}", "danger")
    return redirect(url_for('admin.admin_dashboard'))

@bp.route('/admin/question/delete/<int:question_id>', methods=['POST'])
@admin_required
def delete_question(question_id):
    try:
        with get_main_db() as cur:
            cur.execute("DELETE FROM questions WHERE id = %s;", (question_id,))
        flash("Question deleted successfully.", "warning")
    except Exception as e:
        flash(f"Failed to delete question: {str(e)}", "danger")
    return redirect(url_for('admin.admin_dashboard'))

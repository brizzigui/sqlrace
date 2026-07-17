from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from routes.auth import login_required
from database import get_main_db
from judge import evaluate_submission
from datetime import datetime

bp = Blueprint('contest', __name__)

@bp.route('/contests')
@login_required
def contests_list():
    now = datetime.now()
    with get_main_db() as cur:
        # Fetch all contests
        cur.execute("SELECT id, title, description, start_time, end_time FROM contests ORDER BY start_time ASC;")
        all_contests = cur.fetchall()
        
    active = []
    upcoming = []
    past = []
    
    for c in all_contests:
        # c is (id, title, description, start_time, end_time)
        start = c[3]
        end = c[4]
        contest_dict = {
            'id': c[0],
            'title': c[1],
            'description': c[2],
            'start_time': start,
            'end_time': end,
            'start_formatted': start.strftime('%Y-%m-%d %H:%M:%S'),
            'end_formatted': end.strftime('%Y-%m-%d %H:%M:%S')
        }
        if start <= now <= end:
            active.append(contest_dict)
        elif now < start:
            upcoming.append(contest_dict)
        else:
            past.append(contest_dict)
            
    return render_template('contests.html', active=active, upcoming=upcoming, past=past)

@bp.route('/contest/<int:contest_id>')
@login_required
def contest_dashboard(contest_id):
    team_id = session.get('team_id')
    now = datetime.now()
    
    with get_main_db() as cur:
        # Fetch contest details
        cur.execute("SELECT id, title, description, start_time, end_time FROM contests WHERE id = %s;", (contest_id,))
        contest = cur.fetchone()
        if not contest:
            flash('Contest not found.', 'danger')
            return redirect(url_for('contest.contests_list'))
            
        # Fetch questions for this contest
        cur.execute("SELECT id, title, points FROM questions WHERE contest_id = %s ORDER BY id ASC;", (contest_id,))
        questions = cur.fetchall()
        
        # Check status for each question
        question_list = []
        for q in questions:
            q_id, q_title, q_points = q
            cur.execute("""
                SELECT status FROM submissions 
                WHERE team_id = %s AND question_id = %s 
                ORDER BY submitted_at DESC;
            """, (team_id, q_id))
            subs = cur.fetchall()
            
            status = 'Unattempted'
            if subs:
                status = 'Attempted'
                for s in subs:
                    if s[0] == 'Accepted':
                        status = 'Accepted'
                        break
                        
            question_list.append({
                'id': q_id,
                'title': q_title,
                'points': q_points,
                'status': status
            })
            
    start_time = contest[3]
    end_time = contest[4]
    
    # Calculate contest state
    status_label = "Active"
    if now < start_time:
        status_label = "Upcoming"
    elif now > end_time:
        status_label = "Past"
        
    contest_data = {
        'id': contest[0],
        'title': contest[1],
        'description': contest[2],
        'start_time': start_time.isoformat(),
        'end_time': end_time.isoformat(),
        'status': status_label
    }
    
    return render_template('contest.html', contest=contest_data, questions=question_list)

@bp.route('/contest/<int:contest_id>/question/<int:question_id>')
@login_required
def question_details(contest_id, question_id):
    team_id = session.get('team_id')
    now = datetime.now()
    
    with get_main_db() as cur:
        # Validate contest and question relation
        cur.execute("SELECT id, start_time, end_time FROM contests WHERE id = %s;", (contest_id,))
        contest = cur.fetchone()
        if not contest:
            flash('Contest not found.', 'danger')
            return redirect(url_for('contest.contests_list'))
            
        cur.execute("""
            SELECT id, title, description, init_sql, points 
            FROM questions 
            WHERE id = %s AND contest_id = %s;
        """, (question_id, contest_id))
        question = cur.fetchone()
        if not question:
            flash('Question not found in this contest.', 'danger')
            return redirect(url_for('contest.contest_dashboard', contest_id=contest_id))
            
        # Fetch team's submissions for this question
        cur.execute("""
            SELECT id, query, status, error_message, submitted_at 
            FROM submissions 
            WHERE team_id = %s AND question_id = %s 
            ORDER BY submitted_at DESC;
        """, (team_id, question_id))
        submissions = cur.fetchall()
        
    start_time = contest[1]
    end_time = contest[2]
    
    # Render question workspace
    q_data = {
        'id': question[0],
        'title': question[1],
        'description': question[2],
        'init_sql': question[3],
        'points': question[4]
    }
    
    # Format submissions
    formatted_subs = []
    for sub in submissions:
        formatted_subs.append({
            'id': sub[0],
            'query': sub[1],
            'status': sub[2],
            'error_message': sub[3],
            'submitted_at': sub[4].strftime('%Y-%m-%d %H:%M:%S')
        })
        
    contest_data = {
        'id': contest_id,
        'is_active': start_time <= now <= end_time,
        'start_time': start_time.isoformat(),
        'end_time': end_time.isoformat()
    }
    
    return render_template('question_editor.html', contest=contest_data, question=q_data, submissions=formatted_subs)

@bp.route('/contest/<int:contest_id>/question/<int:question_id>/submit', methods=['POST'])
@login_required
def submit_query(contest_id, question_id):
    team_id = session.get('team_id')
    now = datetime.now()
    
    # Parse request JSON or Form
    if request.is_json:
        data = request.get_json()
        user_query = data.get('query', '').strip()
    else:
        user_query = request.form.get('query', '').strip()
        
    if not user_query:
        return jsonify({
            'status': 'Runtime Error',
            'error_message': 'Query cannot be empty.'
        }), 400
        
    with get_main_db() as cur:
        # Check contest status
        cur.execute("SELECT start_time, end_time FROM contests WHERE id = %s;", (contest_id,))
        contest = cur.fetchone()
        if not contest:
            return jsonify({'status': 'Runtime Error', 'error_message': 'Contest not found.'}), 404
            
        start_time, end_time = contest
        if now < start_time:
            return jsonify({'status': 'Runtime Error', 'error_message': 'Contest has not started yet.'}), 403
        if now > end_time:
            return jsonify({'status': 'Runtime Error', 'error_message': 'Contest has already ended.'}), 403
            
        # Get question
        cur.execute("SELECT init_sql, solution_sql FROM questions WHERE id = %s AND contest_id = %s;", (question_id, contest_id))
        question = cur.fetchone()
        if not question:
            return jsonify({'status': 'Runtime Error', 'error_message': 'Question not found.'}), 404
            
        init_sql, solution_sql = question

    # Run the judge (sandbox database)
    status, error_message, user_cols, user_rows = evaluate_submission(init_sql, solution_sql, user_query)
    
    # Save submission metadata to main database
    with get_main_db() as cur:
        cur.execute("""
            INSERT INTO submissions (team_id, question_id, query, status, error_message, submitted_at)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, submitted_at;
        """, (team_id, question_id, user_query, status, error_message, now))
        sub_id, sub_time = cur.fetchone()
        
    # Serialize row values (e.g. convert date objects to string for JSON serialization)
    serializable_rows = []
    for r in user_rows:
        serializable_rows.append([str(val) if val is not None else None for val in r])
        
    return jsonify({
        'submission_id': sub_id,
        'submitted_at': sub_time.strftime('%Y-%m-%d %H:%M:%S'),
        'status': status,
        'error_message': error_message,
        'columns': user_cols,
        'rows': serializable_rows[:100] # Limit response to first 100 rows for performance
    })

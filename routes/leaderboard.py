from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from translations import translate as _
from routes.auth import login_required
from database import get_main_db
from datetime import datetime

bp = Blueprint('leaderboard', __name__)

def compute_contest_leaderboard(contest_id):
    with get_main_db() as cur:
        # Get contest details
        cur.execute("SELECT id, title, start_time, end_time FROM contests WHERE id = %s;", (contest_id,))
        contest = cur.fetchone()
        if not contest:
            return None, None, None
            
        contest_id_val, title, start_time, end_time = contest
        
        # Get questions for the contest via join table
        cur.execute("""
            SELECT q.id, q.title 
            FROM questions q
            JOIN contest_questions cq ON q.id = cq.question_id
            WHERE cq.contest_id = %s 
            ORDER BY q.id ASC;
        """, (contest_id,))
        questions = cur.fetchall()
        q_list = [{'id': q[0], 'title': q[1]} for q in questions]
        q_ids = [q[0] for q in questions]
        
        # Get all teams who have entered the contest (including admins)
        cur.execute("""
            SELECT t.id, t.username 
            FROM teams t
            JOIN contest_participants cp ON t.id = cp.team_id
            WHERE cp.contest_id = %s;
        """, (contest_id,))
        teams = cur.fetchall()
        
        # Get all submissions within the contest timeframe to this contest, sorted by time
        cur.execute("""
            SELECT s.team_id, s.question_id, s.status, s.submitted_at 
            FROM submissions s
            WHERE s.contest_id = %s AND s.submitted_at BETWEEN %s AND %s
            ORDER BY s.submitted_at ASC;
        """, (contest_id, start_time, end_time))
        submissions = cur.fetchall()

    # Map team submissions
    team_subs = {t[0]: {q_id: [] for q_id in q_ids} for t in teams}
    for sub in submissions:
        t_id, q_id, status, sub_time = sub
        if t_id in team_subs and q_id in team_subs[t_id]:
            team_subs[t_id][q_id].append({
                'status': status,
                'time': sub_time
            })
            
    board_data = []
    
    for team_id, username in teams:
        solved_count = 0
        total_penalty = 0
        problem_details = {}
        
        for q_id in q_ids:
            subs = team_subs[team_id][q_id]
            solved = False
            attempts_before_ac = 0
            penalty = 0
            
            for s in subs:
                if solved:
                    break # Submissions after first AC do not count
                if s['status'] == 'Accepted':
                    solved = True
                    elapsed_minutes = int((s['time'] - start_time).total_seconds() / 60)
                    penalty = elapsed_minutes + (attempts_before_ac * 20)
                    total_penalty += penalty
                    solved_count += 1
                else:
                    # Wrong Answer / Runtime Error
                    attempts_before_ac += 1
                    
            problem_details[q_id] = {
                'solved': solved,
                'attempts': attempts_before_ac + (1 if solved else 0),
                'penalty': penalty if solved else 0
            }
            
        board_data.append({
            'team_id': team_id,
            'username': username,
            'solved_count': solved_count,
            'total_penalty': total_penalty,
            'problems': problem_details
        })
        
    # Sort: solved_count DESC, total_penalty ASC, username ASC
    board_data.sort(key=lambda x: (-x['solved_count'], x['total_penalty'], x['username']))
    
    # Assign ranks
    for idx, team in enumerate(board_data):
        team['rank'] = idx + 1
        
    contest_data = {
        'id': contest_id_val,
        'title': title,
        'start_time': start_time.isoformat(),
        'end_time': end_time.isoformat()
    }
    
    return contest_data, q_list, board_data

@bp.route('/contest/<int:contest_id>/leaderboard')
@login_required
def show_leaderboard(contest_id):
    contest_data, questions, board_data = compute_contest_leaderboard(contest_id)
    if not contest_data:
        flash(_('flash_contest_not_found'), 'danger')
        return redirect(url_for('contest.contests_list'))
        
    return render_template(
        'leaderboard.html', 
        contest=contest_data, 
        questions=questions, 
        leaderboard=board_data
    )

@bp.route('/contest/<int:contest_id>/leaderboard/data')
@login_required
def leaderboard_json(contest_id):
    contest_data, questions, board_data = compute_contest_leaderboard(contest_id)
    if not contest_data:
        return jsonify({'error': _('flash_contest_not_found')}), 404
        
    return jsonify({
        'contest': contest_data,
        'questions': questions,
        'leaderboard': board_data
    })

@bp.route('/leaderboard')
@login_required
def global_leaderboard():
    with get_main_db() as cur:
        # Rank by solved count DESC, total submissions ASC (meaning fewer attempts to solve issues is better), then team name ASC
        cur.execute("""
            SELECT t.id, t.username, t.avatar_seed,
                   (SELECT COUNT(DISTINCT question_id) FROM submissions WHERE team_id = t.id AND status = 'Accepted') as solved_count,
                   (SELECT COUNT(*) FROM submissions WHERE team_id = t.id) as total_submissions
            FROM teams t
            ORDER BY solved_count DESC, total_submissions ASC, t.username ASC;
        """)
        leaderboard_rows = cur.fetchall()
        
    leaderboard_data = []
    for idx, row in enumerate(leaderboard_rows):
        leaderboard_data.append({
            'rank': idx + 1,
            'team_id': row[0],
            'username': row[1],
            'avatar_seed': row[2] or '',
            'solved_count': row[3],
            'total_submissions': row[4]
        })
        
    return render_template('global_leaderboard.html', leaderboard=leaderboard_data)

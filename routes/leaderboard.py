from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from translations import translate as _
from routes.auth import login_required
from database import get_main_db
from datetime import datetime, timedelta

bp = Blueprint('leaderboard', __name__)

def compute_contest_leaderboard(contest_id, is_admin=False, freeze_override=None):
    now = datetime.now()
    with get_main_db() as cur:
        # Get contest details including blind configuration
        cur.execute("""
            SELECT id, title, start_time, end_time,
                   COALESCE(blind_duration_minutes, 0),
                   COALESCE(reveal_mode, 'immediate'),
                   blind_started_at,
                   COALESCE(revealed, FALSE)
            FROM contests WHERE id = %s;
        """, (contest_id,))
        contest = cur.fetchone()
        if not contest:
            return None, None, None
            
        (contest_id_val, title, start_time, end_time, 
         blind_duration, reveal_mode, blind_started_at, revealed) = contest
         
        # Ensure blind_started_at is calculated if duration is set
        if blind_duration > 0 and not blind_started_at:
            blind_started_at = end_time - timedelta(minutes=blind_duration)
            
        has_blind = (blind_duration > 0 and blind_started_at is not None)
        
        # Check automatic release for 'immediate' mode after contest end
        if has_blind and reveal_mode == 'immediate' and now >= end_time and not revealed:
            try:
                cur.execute("UPDATE contests SET revealed = TRUE WHERE id = %s;", (contest_id,))
                revealed = True
            except Exception:
                revealed = True
                
        # Determine blind states
        in_blind_period = has_blind and (blind_started_at <= now < end_time)
        delayed_pending = has_blind and (now >= end_time) and (reveal_mode == 'delayed') and (not revealed)
        is_frozen_for_public = has_blind and (in_blind_period or delayed_pending)
        
        if freeze_override is not None:
            is_frozen = freeze_override
        else:
            # Admins see real-time scoreboard unless explicit freeze override requested
            is_frozen = is_frozen_for_public if not is_admin else False
        
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
        
        # Cutoff timestamp: frozen scoreboard only considers submissions before blind_started_at
        sub_cutoff = blind_started_at if (is_frozen and blind_started_at) else end_time
        
        cur.execute("""
            SELECT s.id, s.team_id, s.question_id, s.status, s.submitted_at 
            FROM submissions s
            WHERE s.contest_id = %s AND s.submitted_at >= %s AND s.submitted_at <= %s
            ORDER BY s.submitted_at ASC;
        """, (contest_id, start_time, sub_cutoff))
        submissions = cur.fetchall()

    # Map team submissions
    team_subs = {t[0]: {q_id: [] for q_id in q_ids} for t in teams}
    for sub in submissions:
        sub_id, t_id, q_id, status, sub_time = sub
        if t_id in team_subs and q_id in team_subs[t_id]:
            is_blind_sub = has_blind and (sub_time >= blind_started_at and sub_time <= end_time)
            team_subs[t_id][q_id].append({
                'id': sub_id,
                'status': status,
                'time': sub_time,
                'is_blind_submission': is_blind_sub
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
        'end_time': end_time.isoformat(),
        'blind_duration_minutes': blind_duration,
        'reveal_mode': reveal_mode,
        'blind_started_at': blind_started_at.isoformat() if blind_started_at else None,
        'revealed': revealed,
        'has_blind': has_blind,
        'in_blind_period': in_blind_period,
        'delayed_pending': delayed_pending,
        'is_frozen': is_frozen,
        'is_frozen_for_public': is_frozen_for_public,
        'is_admin_view': (is_admin and is_frozen_for_public)
    }
    
    return contest_data, q_list, board_data

@bp.route('/contest/<int:contest_id>/leaderboard')
@login_required
def show_leaderboard(contest_id):
    is_admin = session.get('is_admin', False)
    view_param = request.args.get('view')
    freeze_override = None
    if is_admin and view_param == 'frozen':
        freeze_override = True
    elif is_admin and view_param == 'realtime':
        freeze_override = False

    contest_data, questions, board_data = compute_contest_leaderboard(
        contest_id, is_admin=is_admin, freeze_override=freeze_override
    )
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
    is_admin = session.get('is_admin', False)
    view_param = request.args.get('view')
    freeze_override = None
    if is_admin and view_param == 'frozen':
        freeze_override = True
    elif is_admin and view_param == 'realtime':
        freeze_override = False

    contest_data, questions, board_data = compute_contest_leaderboard(
        contest_id, is_admin=is_admin, freeze_override=freeze_override
    )
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
        # Rank primarily by total_score (sum of difficulties of solved questions) DESC,
        # then solved count DESC, total submissions ASC, and team name ASC
        cur.execute("""
            SELECT t.id, t.username, t.avatar_seed,
                   (SELECT COUNT(DISTINCT question_id) FROM submissions WHERE team_id = t.id AND status = 'Accepted') as solved_count,
                   COALESCE((
                       SELECT SUM(q.difficulty)
                       FROM questions q
                       WHERE q.id IN (
                           SELECT DISTINCT question_id
                           FROM submissions
                           WHERE team_id = t.id AND status = 'Accepted'
                       )
                   ), 0) as total_score,
                   (SELECT COUNT(*) FROM submissions WHERE team_id = t.id) as total_submissions
            FROM teams t
            ORDER BY total_score DESC, solved_count DESC, total_submissions ASC, t.username ASC;
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
            'total_score': row[4],
            'total_submissions': row[5]
        })
        
    return render_template('global_leaderboard.html', leaderboard=leaderboard_data)

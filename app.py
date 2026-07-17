import os
from flask import Flask, redirect, url_for
from flask_session import Session
from dotenv import load_dotenv
from database import init_pools

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-sqlrace-key')
    
    # Configure Server-side Session using filesystem to prevent tamper-prone cookie session
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_PERMANENT'] = False
    app.config['SESSION_USE_SIGNER'] = True
    Session(app)
    
    # Initialize database pools
    init_pools()
    
    # Register blueprints
    from routes.auth import bp as auth_bp
    from routes.admin import bp as admin_bp
    from routes.contest import bp as contest_bp
    from routes.leaderboard import bp as leaderboard_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(contest_bp)
    app.register_blueprint(leaderboard_bp)
    
    @app.route('/')
    def index():
        return redirect(url_for('contest.contests_list'))
        
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)

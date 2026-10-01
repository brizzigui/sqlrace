import os
from datetime import timedelta
from flask import Flask, redirect, url_for, render_template, jsonify
from flask_session import Session
from dotenv import load_dotenv
from database import init_pools
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-sqlrace-key')
    app.wsgi_app = ProxyFix(
        app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
    )

    # Configure Server-side Session using filesystem to prevent tamper-prone cookie session
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_PERMANENT'] = True
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
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

    from flask import session, request
    from translations import TRANSLATIONS

    @app.context_processor
    def inject_translation():
        lang = session.get('lang', 'en')
        def translate(key, **kwargs):
            lang_dict = TRANSLATIONS.get(lang, TRANSLATIONS['en'])
            # Return value or default to key
            val = lang_dict.get(key, TRANSLATIONS['en'].get(key, key))
            if kwargs:
                try:
                    return val.format(**kwargs)
                except Exception:
                    pass
            return val
        return dict(_=translate, current_lang=lang)

    import markdown
    @app.template_filter('markdown')
    def render_markdown(text):
        if not text:
            return ""
        html = markdown.markdown(text, extensions=['fenced_code', 'tables', 'nl2br', 'sane_lists'])
        # Wrap generated tables in a responsive scroll container with the premium data-table class
        html = html.replace('<table>', '<div class="table-scroll"><table class="data-table">').replace('</table>', '</table></div>')
        return html

    @app.route('/set_lang/<lang>')
    def set_lang(lang):
        if lang in ['en', 'pt']:
            session['lang'] = lang
        return redirect(request.referrer or url_for('contest.contests_list'))
    
    @app.route('/')
    def index():
        return redirect(url_for('contest.contests_list'))

    # Limit max request body size to 10MB
    app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

    @app.errorhandler(413)
    def request_entity_too_large(e):
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.path == '/admin/upload_image':
            return jsonify({'error': 'File size exceeds maximum limit of 10MB'}), 413
        return render_template('404.html'), 413

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404
        
    return app

if __name__ == '__main__':
    app = create_app()
    port = int(os.getenv('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)

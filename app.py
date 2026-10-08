import os
from flask import Flask, render_template, send_from_directory, jsonify, session, request, redirect, url_for, flash
from config import Config
from database import init_db, get_db
from routes import register_blueprints
from utils.helpers import (
    format_currency, format_date, format_datetime,
    get_gym_settings, is_gym_open, get_now
)

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Ensure upload directories exist
    os.makedirs(Config.MEMBERS_UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(Config.TRAINERS_UPLOAD_FOLDER, exist_ok=True)
    
    # Initialize MongoDB connection & indexes
    db = init_db(app)
    try:
        if db is not None and db.admins.count_documents({}) == 0:
            from seed import seed_database
            seed_database(db)
    except Exception as e:
        app.logger.warning(f"Auto-seed check note: {e}")
    
    # Register blueprints
    register_blueprints(app)
    
    # URL Security: Strict Role-Based Access Control
    @app.before_request
    def enforce_role_access():
        path = request.path
        if path.startswith('/static') or path.startswith('/uploads') or path in ['/login', '/logout', '/register']:
            return None
            
        if not session.get('logged_in'):
            return None
            
        role = str(session.get('role', 'admin')).lower()
        
        # 1. Member restrictions
        if role == 'member':
            admin_restricted = ['/members', '/trainers', '/memberships', '/reports', '/settings', '/payments']
            if path in ['/', '/dashboard'] or any(path.startswith(p) for p in admin_restricted) or path.startswith('/trainer'):
                if request.is_json or path.startswith('/api/'):
                    return jsonify({'success': False, 'message': 'Access Denied: You do not have permission to access this resource.'}), 403
                flash('Access Denied: You do not have permission to access this page.', 'danger')
                return redirect(url_for('member.dashboard'))
                
        # 2. Trainer restrictions
        elif role == 'trainer':
            admin_restricted = ['/members', '/trainers', '/memberships', '/reports', '/settings', '/payments']
            if path in ['/', '/dashboard'] or any(path.startswith(p) for p in admin_restricted) or path.startswith('/member'):
                if request.is_json or path.startswith('/api/'):
                    return jsonify({'success': False, 'message': 'Access Denied: You do not have permission to access this resource.'}), 403
                flash('Access Denied: You do not have permission to access this page.', 'danger')
                return redirect(url_for('trainer.dashboard'))

    # Auto-persist mock database changes to local disk
    @app.after_request
    def auto_persist_db(response):
        if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
            try:
                from database.db import save_mock_db
                save_mock_db()
            except Exception:
                pass
        return response
    @app.template_filter('currency')
    def filter_currency(val):
        return format_currency(val)
        
    @app.template_filter('format_date')
    def filter_date(val, fmt="%d %b %Y"):
        return format_date(val, fmt)
        
    @app.template_filter('format_datetime')
    def filter_datetime(val, fmt="%d %b %Y, %I:%M %p"):
        return format_datetime(val, fmt)
        
    # Global context processor
    @app.context_processor
    def inject_globals():
        settings = get_gym_settings()
        gym_open = is_gym_open(settings)
        unread_count = 0
        pending_requests_count = 0
        if session.get('logged_in'):
            try:
                db = get_db()
                unread_count = db.notifications.count_documents({"is_read": False})
                if str(session.get('role', '')).lower() == 'admin':
                    pending_requests_count = db.members.count_documents({"status": {"$in": ["Pending", "pending"]}})
            except Exception:
                unread_count = 0
                pending_requests_count = 0
                
        return {
            "gym_settings": settings,
            "gym_open": gym_open,
            "unread_notif_count": unread_count,
            "pending_requests_count": pending_requests_count,
            "current_year": get_now().year,
            "now_dt": get_now()
        }
        
    # Serve user uploads
    @app.route('/uploads/<path:filename>')
    def serve_uploaded_file(filename):
        return send_from_directory(Config.UPLOAD_FOLDER, filename)
        
    # Error handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404
        
    @app.errorhandler(403)
    def access_forbidden(e):
        return render_template('403.html'), 403
        
    @app.errorhandler(500)
    def server_error(e):
        return render_template('500.html'), 500

    return app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # Running in local development mode
    app.run(host='127.0.0.1', port=port, debug=True, use_reloader=False)

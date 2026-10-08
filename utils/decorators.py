from functools import wraps
from flask import session, redirect, url_for, flash, request, jsonify

def login_required(f):
    """
    Ensures user is authenticated. Supports both unified user_id and legacy admin_id.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id') or session.get('admin_id')
        if not session.get('logged_in') or not user_id:
            if session.get('logged_in') and not user_id:
                session.clear()
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'success': False, 'message': 'Authentication required. Please log in.'}), 401
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*allowed_roles):
    """
    Restricts route access to specific role(s) e.g. 'admin', 'trainer', 'member'.
    If unauthorized, blocks access with 403 or redirects to their authorized dashboard.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = session.get('user_id') or session.get('admin_id')
            if not session.get('logged_in') or not user_id:
                if session.get('logged_in') and not user_id:
                    session.clear()
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'success': False, 'message': 'Authentication required. Please log in.'}), 401
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login', next=request.path))
            
            user_role = str(session.get('role', '')).lower()
            allowed = [str(r).lower() for r in allowed_roles]
            
            # Legacy admin fallback
            if session.get('admin_id') and not user_role:
                user_role = 'admin'
                session['role'] = 'admin'
                
            if user_role not in allowed:
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'success': False, 'message': 'Access Denied: You do not have permission to access this resource.'}), 403
                
                flash('Access Denied: You do not have permission to access this page.', 'danger')
                
                # Redirect to user's respective authorized dashboard
                if user_role == 'trainer':
                    return redirect(url_for('trainer.dashboard'))
                elif user_role == 'member':
                    return redirect(url_for('member.dashboard'))
                else:
                    return redirect(url_for('dashboard.index'))
                    
            return f(*args, **kwargs)
        return decorated_function
    return decorator

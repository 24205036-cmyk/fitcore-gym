from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import get_db
from utils.auth import verify_password
from utils.helpers import get_now

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('logged_in'):
        return redirect(url_for('dashboard.index'))
        
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        remember = bool(request.form.get('remember'))
        
        if not username or not password:
            flash('Please enter both username and password.', 'danger')
            return render_template('login.html', username=username)
            
        db = get_db()
        admin = db.admins.find_one({'username': username})
        
        if admin and verify_password(admin.get('password', ''), password):
            # Update last login
            db.admins.update_one({'_id': admin['_id']}, {'$set': {'last_login': get_now()}})
            
            session.clear()
            session['logged_in'] = True
            session['admin_id'] = str(admin['_id'])
            session['admin_username'] = admin['username']
            session['admin_name'] = admin.get('full_name', 'Administrator')
            session['admin_email'] = admin.get('email', 'admin@fitcore.local')
            if remember:
                session.permanent = True
                
            flash(f"Welcome back, {session['admin_name']}!", 'success')
            next_url = request.args.get('next')
            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect(url_for('dashboard.index'))
        else:
            flash('Invalid username or password. Please try again.', 'danger')
            return render_template('login.html', username=username)
            
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out securely.', 'info')
    return redirect(url_for('auth.login'))

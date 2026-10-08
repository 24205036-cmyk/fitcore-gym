import re
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, make_response
from database import get_db
from utils.auth import verify_password, hash_password
from utils.helpers import get_now
from utils.ids import get_next_member_id, get_next_user_id
from utils.validators import validate_registration_form

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('logged_in'):
        user_id = session.get('user_id') or session.get('admin_id')
        if not user_id:
            # Clear corrupt or stale partial session
            session.clear()
        else:
            role = str(session.get('role', 'admin')).lower()
            if role == 'trainer':
                return redirect(url_for('trainer.dashboard'))
            elif role == 'member':
                return redirect(url_for('member.dashboard'))
            return redirect(url_for('dashboard.index'))
        
    if request.method == 'POST':
        identifier = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        remember = bool(request.form.get('remember'))
        
        if not identifier or not password:
            flash('Please enter both email/username and password.', 'danger')
            return render_template('login.html', username=identifier)
            
        db = get_db()
        
        try:
            # 1. First look up in unified users collection
            user = db.users.find_one({
                "$or": [
                    {"email": {"$regex": f"^{re.escape(identifier)}$", "$options": "i"}},
                    {"username": identifier},
                    {"user_id": identifier},
                    {"phone": identifier}
                ]
            })
            
            # 2. Legacy fallback to admins collection
            if not user:
                admin_doc = db.admins.find_one({
                    "$or": [
                        {"username": identifier},
                        {"email": {"$regex": f"^{re.escape(identifier)}$", "$options": "i"}}
                    ]
                })
                if admin_doc:
                    user = {
                        "_id": admin_doc["_id"],
                        "user_id": "USR_ADMIN",
                        "username": admin_doc.get("username", "admin"),
                        "name": admin_doc.get("full_name", "Admin Manager"),
                        "email": admin_doc.get("email", "admin@fitcore.local"),
                        "password": admin_doc.get("password"),
                        "role": "admin",
                        "status": "active"
                    }
        except Exception as e:
            flash("Database connection error: Please ensure your current IP address is whitelisted in MongoDB Atlas Network Access.", "danger")
            return render_template('login.html', username=identifier)

        # 3. Check trainer by email or ID if user record not in users yet
        if not user:
            trainer_doc = db.trainers.find_one({
                "$or": [
                    {"email": {"$regex": f"^{re.escape(identifier)}$", "$options": "i"}},
                    {"trainer_id": identifier}
                ]
            })
            if trainer_doc and trainer_doc.get('password'):
                user = {
                    "_id": trainer_doc["_id"],
                    "user_id": f"USR_{trainer_doc['trainer_id']}",
                    "trainer_id": trainer_doc["trainer_id"],
                    "name": trainer_doc.get("name"),
                    "email": trainer_doc.get("email"),
                    "password": trainer_doc.get("password"),
                    "role": "trainer",
                    "status": trainer_doc.get("status", "Active").lower()
                }

        # 4. Check member by email or ID if user record not in users yet
        if not user:
            member_doc = db.members.find_one({
                "$or": [
                    {"email": {"$regex": f"^{re.escape(identifier)}$", "$options": "i"}},
                    {"member_id": identifier}
                ]
            })
            if member_doc and member_doc.get('password'):
                user = {
                    "_id": member_doc["_id"],
                    "user_id": f"USR_{member_doc['member_id']}",
                    "member_id": member_doc["member_id"],
                    "name": member_doc.get("full_name"),
                    "email": member_doc.get("email"),
                    "password": member_doc.get("password"),
                    "role": "member",
                    "status": member_doc.get("status", "Active").lower()
                }
                
        if user and verify_password(user.get('password', ''), password):
            # Check account status
            account_status = str(user.get('status', 'active')).lower()
            if account_status == 'pending':
                flash('Registration submitted successfully. Waiting for Admin approval.', 'warning')
                return render_template('login.html', username=identifier)
            elif account_status == 'rejected':
                rejection_reason = user.get('rejection_reason')
                if not rejection_reason and user.get('member_id'):
                    m_doc = db.members.find_one({"member_id": user['member_id']})
                    if m_doc and m_doc.get('rejection_reason'):
                        rejection_reason = m_doc.get('rejection_reason')
                rejection_reason = rejection_reason or 'Registration information is incomplete.'
                flash(f'Your registration request was rejected: {rejection_reason}', 'danger')
                return render_template('login.html', username=identifier)
            elif account_status in ['inactive', 'suspended']:
                flash('Your account is currently inactive. Please contact the gym administrator.', 'danger')
                return render_template('login.html', username=identifier)
                
            # Update last login timestamp
            try:
                db.users.update_one({'_id': user['_id']}, {'$set': {'last_login': get_now()}})
            except Exception:
                pass
                
            session.clear()
            session['logged_in'] = True
            session['user_id'] = str(user.get('user_id') or user['_id'])
            role = str(user.get('role', 'member')).lower()
            session['role'] = role
            session['name'] = user.get('name') or user.get('full_name', 'User')
            session['email'] = user.get('email', '')
            
            if role == 'admin':
                session['admin_id'] = str(user['_id'])
                session['admin_username'] = user.get('username', 'admin')
                session['admin_name'] = session['name']
            elif role == 'trainer':
                session['trainer_id'] = user.get('trainer_id')
            elif role == 'member':
                session['member_id'] = user.get('member_id')
                
            if remember:
                session.permanent = True
                
            flash(f"Welcome back, {session['name']}!", 'success')
            
            next_url = request.args.get('next')
            if next_url:
                from urllib.parse import urlparse
                parsed = urlparse(next_url)
                if not parsed.netloc and parsed.path.startswith('/'):
                    return redirect(parsed.path)
                elif parsed.netloc in [request.host, '127.0.0.1:5000', 'localhost:5000'] and parsed.path.startswith('/'):
                    return redirect(parsed.path)
                
            # Role-based redirection
            if role == 'admin':
                return redirect(url_for('dashboard.index'))
            elif role == 'trainer':
                return redirect(url_for('trainer.dashboard'))
            elif role == 'member':
                return redirect(url_for('member.dashboard'))
            else:
                return redirect(url_for('dashboard.index'))
        else:
            flash('Invalid email/username or password. Please try again.', 'danger')
            return render_template('login.html', username=identifier)
            
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if session.get('logged_in'):
        user_id = session.get('user_id') or session.get('admin_id')
        if not user_id:
            session.clear()
        else:
            role = str(session.get('role', 'admin')).lower()
            if role == 'trainer':
                return redirect(url_for('trainer.dashboard'))
            elif role == 'member':
                return redirect(url_for('member.dashboard'))
            return redirect(url_for('dashboard.index'))
        
    db = get_db()
    plans = list(db.membership_plans.find({"status": "Active"}))
    
    if request.method == 'POST':
        form_data = request.form.to_dict()
        is_valid, err_msg = validate_registration_form(form_data)
        if not is_valid:
            flash(err_msg, 'danger')
            return render_template('register.html', form=form_data, plans=plans)
            
        email = form_data.get('email', '').strip().lower()
        
        # Check duplicate email
        existing_user = db.users.find_one({"email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}})
        existing_member = db.members.find_one({"email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}})
        if existing_user or existing_member:
            flash('An account with this email address already exists. Please sign in.', 'danger')
            return render_template('register.html', form=form_data, plans=plans)
            
        full_name = form_data.get('full_name', '').strip()
        phone = form_data.get('phone', '').strip()
        password = form_data.get('password', '')
        gender = form_data.get('gender', 'Male')
        dob = form_data.get('date_of_birth', '')
        address = form_data.get('address', '').strip()
        selected_plan_id = form_data.get('plan_id', '')
        
        plan = db.membership_plans.find_one({"plan_id": selected_plan_id}) if selected_plan_id else None
        if not plan:
            plan = db.membership_plans.find_one() or {"plan_id": "PLAN001", "name": "Standard", "duration_days": 30, "price": 1500}
            
        # Generate sequential IDs
        member_id = get_next_member_id()
        user_id = get_next_user_id()
        hashed = hash_password(password)
        now = get_now()
        
        duration_days = int(plan.get('duration_days', 30))
        start_date = now.strftime("%Y-%m-%d")
        end_date = (now + timedelta(days=duration_days)).strftime("%Y-%m-%d")
        
        # Calculate age if DOB provided
        age = 25
        if dob:
            try:
                dob_dt = datetime.strptime(dob[:10], "%Y-%m-%d")
                age = max(12, (now - dob_dt).days // 365)
            except Exception:
                age = 25

        fitness_goal = form_data.get('fitness_goal', 'General Fitness').strip() or 'General Fitness'

        # 1. Insert into users collection (role is member, status is pending approval)
        user_doc = {
            "user_id": user_id,
            "member_id": member_id,
            "name": full_name,
            "email": email,
            "phone": phone,
            "password": hashed,
            "role": "member",
            "status": "pending",
            "fitness_goal": fitness_goal,
            "created_at": now
        }
        db.users.insert_one(user_doc)
        
        # 2. Insert into members collection with Pending status awaiting Admin review
        member_doc = {
            "member_id": member_id,
            "user_id": user_id,
            "full_name": full_name,
            "email": email,
            "phone": phone,
            "gender": gender,
            "age": age,
            "date_of_birth": dob,
            "address": address,
            "fitness_goal": fitness_goal,
            "plan_id": plan.get("plan_id"),
            "plan_name": plan.get("name"),
            "plan_price": float(plan.get("price", 0)),
            "start_date": start_date,
            "end_date": end_date,
            "join_date": start_date,
            "trainer_id": None,
            "trainer_name": None,
            "status": "Pending",
            "approval_status": "pending",
            "payment_status": "Pending Approval",
            "photo": "",
            "emergency_contact": "",
            "created_at": now,
            "updated_at": now
        }
        db.members.insert_one(member_doc)
        
        # 3. Add system notification for Admin review
        db.notifications.insert_one({
            "title": "New Member Registration Request",
            "message": f"{full_name} ({member_id}) submitted online registration. Goal: {fitness_goal}. Awaiting Admin review.",
            "type": "warning",
            "link": "/members/requests",
            "is_read": False,
            "created_at": now
        })
        
        flash("Registration submitted successfully. Waiting for Admin approval.", "info")
        return redirect(url_for('auth.login'))
        
    return render_template('register.html', plans=plans)

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out securely.', 'info')
    resp = make_response(redirect(url_for('auth.login')))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

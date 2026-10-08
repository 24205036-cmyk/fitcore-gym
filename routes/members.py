from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from bson import ObjectId
from datetime import datetime, timedelta
from database import get_db
from utils.decorators import login_required
from utils.ids import get_next_member_id, get_next_payment_id, get_next_user_id
from utils.auth import hash_password
from utils.helpers import (
    get_now, format_date, format_datetime, format_currency,
    calculate_member_status, save_uploaded_file
)
from utils.validators import validate_member_form
from utils.notifier import log_notification

members_bp = Blueprint('members', __name__, url_prefix='/members')

@members_bp.route('')
@login_required
def list_members():
    db = get_db()
    
    # Query parameters
    search_q = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()
    plan_filter = request.args.get('plan', '').strip()
    trainer_filter = request.args.get('trainer', '').strip()
    sort_by = request.args.get('sort', 'member_id')
    
    # Pagination
    page = int(request.args.get('page', 1))
    per_page = 15
    skip = (page - 1) * per_page
    
    query = {}
    if search_q:
        query['$or'] = [
            {'member_id': {'$regex': search_q, '$options': 'i'}},
            {'full_name': {'$regex': search_q, '$options': 'i'}},
            {'phone': {'$regex': search_q, '$options': 'i'}},
            {'email': {'$regex': search_q, '$options': 'i'}}
        ]
        
    if status_filter:
        query['status'] = status_filter
    if plan_filter:
        query['plan_id'] = plan_filter
    if trainer_filter:
        query['trainer_id'] = trainer_filter
        
    # Auto-update status for expired members in query result
    now_str = get_now().strftime("%Y-%m-%d")
    
    # Update statuses if needed
    db.members.update_many(
        {"status": "Active", "end_date": {"$lt": now_str}},
        {"$set": {"status": "Expired"}}
    )
    
    sort_field = "member_id"
    sort_order = 1
    if sort_by == 'expiry_asc':
        sort_field = "end_date"
        sort_order = 1
    elif sort_by == 'expiry_desc':
        sort_field = "end_date"
        sort_order = -1
    elif sort_by == 'name':
        sort_field = "full_name"
        sort_order = 1
    elif sort_by == 'newest':
        sort_field = "created_at"
        sort_order = -1

    total_records = db.members.count_documents(query)
    members_cursor = db.members.find(query).sort(sort_field, sort_order).skip(skip).limit(per_page)
    members_list = list(members_cursor)
    
    total_pages = (total_records + per_page - 1) // per_page
    
    # Dropdown options
    plans = list(db.membership_plans.find({"status": "Active"}))
    trainers = list(db.trainers.find({"status": "Active"}))

    return render_template(
        'members/list.html',
        members=members_list,
        total_records=total_records,
        page=page,
        total_pages=total_pages,
        search_q=search_q,
        status_filter=status_filter,
        plan_filter=plan_filter,
        trainer_filter=trainer_filter,
        sort_by=sort_by,
        plans=plans,
        trainers=trainers
    )

@members_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_member():
    db = get_db()
    plans = list(db.membership_plans.find({"status": "Active"}))
    trainers = list(db.trainers.find({"status": "Active"}))
    
    if request.method == 'POST':
        form = request.form
        is_valid, err_msg = validate_member_form(form)
        if not is_valid:
            flash(err_msg, 'danger')
            return render_template('members/add.html', form=form, plans=plans, trainers=trainers)
            
        # Get selected plan
        plan = db.membership_plans.find_one({"plan_id": form.get('plan_id')})
        if not plan:
            flash("Selected membership plan not found.", 'danger')
            return render_template('members/add.html', form=form, plans=plans, trainers=trainers)
            
        # Calculate dates
        start_date_str = form.get('start_date') or get_now().strftime("%Y-%m-%d")
        duration_days = int(plan.get('duration_days', 30))
        start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_dt = start_dt + timedelta(days=duration_days)
        end_date_str = form.get('end_date') or end_dt.strftime("%Y-%m-%d")
        
        # Handle file upload
        photo_path = ""
        if 'profile_photo' in request.files:
            file = request.files['profile_photo']
            if file and file.filename:
                photo_path = save_uploaded_file(file, 'members')
                
        # Trainer info
        trainer_id = form.get('trainer_id', '')
        trainer_name = "None"
        if trainer_id:
            trainer = db.trainers.find_one({"trainer_id": trainer_id})
            if trainer:
                trainer_name = trainer.get('name', 'None')
                
        # Generate readable Member ID and User ID
        member_id = get_next_member_id()
        user_id = get_next_user_id()
        
        # Check payment option
        record_payment = form.get('record_payment') == 'yes'
        payment_method = form.get('payment_method', 'Cash')
        payment_status = form.get('payment_status', 'Paid')
        
        new_member = {
            "member_id": member_id,
            "user_id": user_id,
            "full_name": form.get('full_name', '').strip(),
            "photo": photo_path,
            "age": int(form.get('age', 0)) if form.get('age') else None,
            "gender": form.get('gender', 'Other'),
            "phone": form.get('phone', '').strip(),
            "email": form.get('email', '').strip().lower(),
            "address": form.get('address', '').strip(),
            "emergency_contact": form.get('emergency_contact', '').strip(),
            "plan_id": plan['plan_id'],
            "plan_name": plan['name'],
            "plan_price": float(plan['price']),
            "join_date": get_now().strftime("%Y-%m-%d"),
            "start_date": start_date_str,
            "end_date": end_date_str,
            "trainer_id": trainer_id if trainer_id else None,
            "trainer_name": trainer_name,
            "payment_status": payment_status,
            "status": "Active",
            "created_at": get_now(),
            "updated_at": get_now()
        }
        
        db.members.insert_one(new_member)
        
        # Sync with users collection for Member login
        db.users.update_one(
            {"$or": [{"email": new_member["email"]}, {"member_id": member_id}]},
            {
                "$setOnInsert": {
                    "user_id": user_id,
                    "member_id": member_id,
                    "password": hash_password(form.get('password') or "member123"),
                    "created_at": get_now()
                },
                "$set": {
                    "name": new_member["full_name"],
                    "email": new_member["email"],
                    "phone": new_member["phone"],
                    "role": "member",
                    "status": "active"
                }
            },
            upsert=True
        )
        
        # If recording initial payment
        if record_payment:
            pay_id = get_next_payment_id()
            payment_doc = {
                "payment_id": pay_id,
                "member_id": member_id,
                "member_name": new_member["full_name"],
                "plan_id": plan['plan_id'],
                "plan_name": plan['name'],
                "amount": float(plan['price']),
                "payment_date": get_now().strftime("%Y-%m-%d %H:%M:%S"),
                "payment_method": payment_method,
                "transaction_id": form.get('transaction_id', '').strip() or f"TXN-{get_now().strftime('%Y%m%d%H%M%S')}",
                "payment_status": payment_status,
                "remarks": f"Initial membership enrollment ({plan['name']})",
                "created_at": get_now()
            }
            db.payments.insert_one(payment_doc)
            
        # Log notification
        log_notification(
            title="New Member Registered",
            message=f"{new_member['full_name']} joined with {plan['name']} plan.",
            notif_type="success",
            link=f"/members/{member_id}"
        )
        
        flash(f"Member {new_member['full_name']} ({member_id}) registered successfully!", 'success')
        return redirect(url_for('members.view_member', member_id=member_id))
        
    # Default initial dates
    default_start = get_now().strftime("%Y-%m-%d")
    return render_template('members/add.html', plans=plans, trainers=trainers, default_start=default_start)

@members_bp.route('/<member_id>')
@login_required
def view_member(member_id):
    db = get_db()
    member = db.members.find_one({"member_id": member_id})
    if not member:
        flash("Member not found.", 'danger')
        return redirect(url_for('members.list_members'))
        
    # Current status check
    current_status = calculate_member_status(member.get('end_date'), member.get('status', 'Active'))
    if current_status != member.get('status') and member.get('status') not in ['Suspended', 'Inactive']:
        db.members.update_one({"_id": member["_id"]}, {"$set": {"status": current_status}})
        member['status'] = current_status
        
    # Attendance summary
    attendance_records = list(db.attendance.find({"member_id": member_id}).sort("check_in", -1))
    total_visits = len(attendance_records)
    
    # This month visits
    current_month_prefix = get_now().strftime("%Y-%m")
    this_month_visits = sum(1 for a in attendance_records if a.get('check_in', '').startswith(current_month_prefix))
    
    last_visit = attendance_records[0].get('check_in') if attendance_records else None
    
    # Average visit duration in minutes
    durations = [a.get('duration_minutes', 0) for a in attendance_records if a.get('duration_minutes', 0) > 0]
    avg_duration_minutes = round(sum(durations) / len(durations)) if durations else 0
    avg_duration_display = f"{avg_duration_minutes // 60}h {avg_duration_minutes % 60}m" if avg_duration_minutes > 0 else "-"
    
    # Payment summary
    payments = list(db.payments.find({"member_id": member_id}).sort("payment_date", -1))
    total_paid = sum(float(p.get('amount', 0)) for p in payments if p.get('payment_status') == 'Paid')
    last_payment = payments[0] if payments else None
    
    # Pending amount
    pending_amount = sum(float(p.get('amount', 0)) for p in payments if p.get('payment_status') == 'Pending')
    
    # Is currently inside?
    active_checkin = db.attendance.find_one({"member_id": member_id, "status": "Inside"})

    # Active trainers for assignment modal (Admin only)
    trainers = list(db.trainers.find({"status": "Active"}).sort("name", 1))

    return render_template(
        'members/view.html',
        member=member,
        attendance_records=attendance_records[:10],
        total_visits=total_visits,
        this_month_visits=this_month_visits,
        last_visit=last_visit,
        avg_duration_display=avg_duration_display,
        payments=payments,
        total_paid_formatted=format_currency(total_paid),
        pending_amount_formatted=format_currency(pending_amount),
        last_payment=last_payment,
        is_inside=bool(active_checkin),
        active_checkin=active_checkin,
        trainers=trainers
    )

@members_bp.route('/<member_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_member(member_id):
    db = get_db()
    member = db.members.find_one({"member_id": member_id})
    if not member:
        flash("Member not found.", 'danger')
        return redirect(url_for('members.list_members'))
        
    plans = list(db.membership_plans.find({"status": "Active"}))
    trainers = list(db.trainers.find({"status": "Active"}))
    
    if request.method == 'POST':
        form = request.form
        
        # Validate essential fields
        if not form.get('full_name', '').strip():
            flash("Full Name is required.", 'danger')
            return render_template('members/edit.html', member=member, plans=plans, trainers=trainers)
            
        update_data = {
            "full_name": form.get('full_name', '').strip(),
            "age": int(form.get('age', 0)) if form.get('age') else None,
            "gender": form.get('gender', 'Other'),
            "phone": form.get('phone', '').strip(),
            "email": form.get('email', '').strip().lower(),
            "address": form.get('address', '').strip(),
            "emergency_contact": form.get('emergency_contact', '').strip(),
            "status": form.get('status', member.get('status', 'Active')),
            "updated_at": get_now()
        }
        
        # Check trainer change
        trainer_id = form.get('trainer_id', '')
        if trainer_id:
            trainer = db.trainers.find_one({"trainer_id": trainer_id})
            update_data["trainer_id"] = trainer_id
            update_data["trainer_name"] = trainer.get('name', 'None') if trainer else "None"
        else:
            update_data["trainer_id"] = None
            update_data["trainer_name"] = "None"
            
        # Check photo upload
        if 'profile_photo' in request.files:
            file = request.files['profile_photo']
            if file and file.filename:
                new_photo = save_uploaded_file(file, 'members')
                if new_photo:
                    update_data["photo"] = new_photo
                    
        # Update start & end date if explicitly adjusted
        if form.get('start_date'):
            update_data["start_date"] = form.get('start_date')
        if form.get('end_date'):
            update_data["end_date"] = form.get('end_date')
            
        db.members.update_one({"member_id": member_id}, {"$set": update_data})
        
        # Keep users collection synchronized
        member_status = str(update_data.get('status', 'Active')).lower()
        user_status = "active" if member_status == "active" else "inactive"
        db.users.update_one(
            {"member_id": member_id},
            {
                "$set": {
                    "name": update_data["full_name"],
                    "email": update_data["email"],
                    "phone": update_data["phone"],
                    "status": user_status
                }
            }
        )
        
        flash(f"Member details for {update_data['full_name']} updated successfully.", 'success')
        return redirect(url_for('members.view_member', member_id=member_id))
        
    return render_template('members/edit.html', member=member, plans=plans, trainers=trainers)

@members_bp.route('/<member_id>/renew', methods=['GET', 'POST'])
@login_required
def renew_member(member_id):
    db = get_db()
    member = db.members.find_one({"member_id": member_id})
    if not member:
        flash("Member not found.", 'danger')
        return redirect(url_for('members.list_members'))
        
    plans = list(db.membership_plans.find({"status": "Active"}))
    
    if request.method == 'POST':
        plan_id = request.form.get('plan_id')
        plan = db.membership_plans.find_one({"plan_id": plan_id})
        if not plan:
            flash("Selected plan is invalid.", 'danger')
            return redirect(url_for('members.renew_member', member_id=member_id))
            
        # Calculation: intelligent renewal
        # If current end_date has not passed yet, start new plan from current end_date!
        today_date = get_now().date()
        current_end_str = member.get('end_date')
        
        base_date = today_date
        if current_end_str:
            try:
                curr_end = datetime.strptime(current_end_str[:10], "%Y-%m-%d").date()
                if curr_end >= today_date:
                    base_date = curr_end
            except ValueError:
                pass
                
        duration_days = int(plan.get('duration_days', 30))
        new_start_date = base_date.strftime("%Y-%m-%d")
        new_end_date = (base_date + timedelta(days=duration_days)).strftime("%Y-%m-%d")
        
        payment_method = request.form.get('payment_method', 'UPI')
        payment_status = request.form.get('payment_status', 'Paid')
        transaction_id = request.form.get('transaction_id', '').strip() or f"TXN-RNW-{get_now().strftime('%Y%m%d%H%M%S')}"
        
        # Update member
        db.members.update_one(
            {"member_id": member_id},
            {"$set": {
                "plan_id": plan['plan_id'],
                "plan_name": plan['name'],
                "plan_price": float(plan['price']),
                "start_date": new_start_date,
                "end_date": new_end_date,
                "status": "Active",
                "payment_status": payment_status,
                "updated_at": get_now()
            }}
        )
        
        # Record payment
        pay_id = get_next_payment_id()
        db.payments.insert_one({
            "payment_id": pay_id,
            "member_id": member_id,
            "member_name": member.get('full_name'),
            "plan_id": plan['plan_id'],
            "plan_name": plan['name'],
            "amount": float(plan['price']),
            "payment_date": get_now().strftime("%Y-%m-%d %H:%M:%S"),
            "payment_method": payment_method,
            "transaction_id": transaction_id,
            "payment_status": payment_status,
            "remarks": f"Membership Renewal ({plan['name']})",
            "created_at": get_now()
        })
        
        # Notification
        log_notification(
            title="Membership Renewed",
            message=f"{member.get('full_name')} renewed with {plan['name']} until {new_end_date}.",
            notif_type="success",
            link=f"/members/{member_id}"
        )
        
        flash(f"Membership for {member.get('full_name')} renewed successfully until {new_end_date}!", 'success')
        return redirect(url_for('members.view_member', member_id=member_id))
        
    return render_template('members/renew.html', member=member, plans=plans)

@members_bp.route('/<member_id>/delete', methods=['POST'])
@login_required
def delete_member(member_id):
    db = get_db()
    member = db.members.find_one({"member_id": member_id})
    if not member:
        flash("Member not found.", 'danger')
        return redirect(url_for('members.list_members'))
        
    delete_mode = request.form.get('mode', 'permanent').lower()
    full_name = member.get('full_name', 'Member')
    
    if delete_mode == 'deactivate':
        # Deactivate only: preserve records
        db.members.update_one({"member_id": member_id}, {"$set": {"status": "Inactive", "updated_at": get_now()}})
        db.users.update_one({"member_id": member_id}, {"$set": {"status": "inactive"}})
        flash(f"Member {full_name} ({member_id}) was deactivated.", 'warning')
    else:
        # COMPLETE PERMANENT DELETION
        member_email = member.get("email")
        
        # 1. Delete member profile
        db.members.delete_one({"member_id": member_id})
        
        # 2. Delete login user account
        user_query = {"$or": [{"member_id": member_id}]}
        if member_email:
            user_query["$or"].append({"email": member_email})
        db.users.delete_many(user_query)
        
        # 3. Delete attendance records
        db.attendance.delete_many({"member_id": member_id})
        
        # 4. Delete payment records
        db.payments.delete_many({"member_id": member_id})
        
        # 5. Delete workout plans
        db.workout_plans.delete_many({"member_id": member_id})
        
        # 6. Delete training schedules
        db.schedules.delete_many({"member_id": member_id})
        
        # 7. Delete member notifications
        db.notifications.delete_many({"member_id": member_id})
        
        # 8. Log deletion notification for Admin
        log_notification(
            title="Member Completely Deleted",
            message=f"{full_name} ({member_id}) and all associated records were permanently deleted.",
            notif_type="danger",
            link="/members"
        )
        
        flash(f"Member {full_name} ({member_id}) and all associated records were completely deleted from the database.", 'success')
        
    return redirect(url_for('members.list_members'))

@members_bp.route('/<member_id>/toggle-status', methods=['POST'])
@login_required
def toggle_status(member_id):
    db = get_db()
    member = db.members.find_one({"member_id": member_id})
    if not member:
        flash("Member not found.", 'danger')
        return redirect(url_for('members.list_members'))
        
    new_status = "Suspended" if member.get("status") == "Active" else "Active"
    db.members.update_one({"member_id": member_id}, {"$set": {"status": new_status, "updated_at": get_now()}})
    flash(f"Status for {member.get('full_name')} updated to {new_status}.", 'info')
    return redirect(request.referrer or url_for('members.view_member', member_id=member_id))

@members_bp.route('/api/search')
@login_required
def api_search_members():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({"success": True, "members": []})
        
    db = get_db()
    query = {
        '$or': [
            {'member_id': {'$regex': q, '$options': 'i'}},
            {'full_name': {'$regex': q, '$options': 'i'}},
            {'phone': {'$regex': q, '$options': 'i'}},
            {'email': {'$regex': q, '$options': 'i'}}
        ]
    }
    cursor = db.members.find(query).limit(10)
    results = []
    for m in cursor:
        results.append({
            "member_id": m.get("member_id"),
            "full_name": m.get("full_name"),
            "phone": m.get("phone"),
            "plan_name": m.get("plan_name"),
            "status": m.get("status"),
            "end_date": m.get("end_date")
        })
    return jsonify({"success": True, "count": len(results), "members": results})

@members_bp.route('/requests')
@login_required
def member_requests():
    db = get_db()
    status_filter = request.args.get('status', 'Pending').strip()
    
    query = {}
    if status_filter == 'Pending':
        query["status"] = {"$in": ["Pending", "pending"]}
    elif status_filter == 'Rejected':
        query["status"] = {"$in": ["Rejected", "rejected"]}
    elif status_filter == 'Approved':
        query["approval_status"] = "approved"
    else:
        # All
        query["status"] = {"$in": ["Pending", "pending", "Rejected", "rejected", "Active", "active"]}
        
    requests_list = list(db.members.find(query).sort("created_at", -1))
    
    # Active trainers available for assignment
    trainers = list(db.trainers.find({"status": {"$in": ["Active", "active"]}}).sort("name", 1))
    
    pending_count = db.members.count_documents({"status": {"$in": ["Pending", "pending"]}})
    rejected_count = db.members.count_documents({"status": {"$in": ["Rejected", "rejected"]}})
    
    return render_template(
        'members/requests.html',
        requests=requests_list,
        trainers=trainers,
        status_filter=status_filter,
        pending_count=pending_count,
        rejected_count=rejected_count
    )

@members_bp.route('/requests/<member_id>/accept', methods=['POST'])
@login_required
def accept_member_request(member_id):
    db = get_db()
    member = db.members.find_one({"member_id": member_id})
    if not member:
        flash("Member request not found.", 'danger')
        return redirect(url_for('members.member_requests'))
        
    trainer_id = request.form.get('trainer_id', '').strip()
    trainer = db.trainers.find_one({"trainer_id": trainer_id})
    if not trainer:
        flash("Please select a valid active trainer to assign to this member.", 'danger')
        return redirect(url_for('members.member_requests'))
        
    now = get_now()
    assignment_date = now.strftime("%d %b %Y")
    
    # Update Member document
    db.members.update_one(
        {"member_id": member_id},
        {"$set": {
            "status": "Active",
            "approval_status": "approved",
            "trainer_id": trainer["trainer_id"],
            "trainer_name": trainer.get("name", "Trainer"),
            "approved_at": now,
            "updated_at": now
        }}
    )
    
    # Update User document
    db.users.update_one(
        {"$or": [{"member_id": member_id}, {"email": member.get("email")}]},
        {"$set": {
            "status": "active",
            "trainer_id": trainer["trainer_id"],
            "trainer_name": trainer.get("name", "Trainer"),
            "updated_at": now
        }}
    )
    
    # 1. Trainer receives notification: "New member assigned to you."
    fitness_goal = member.get('fitness_goal') or 'General Fitness'
    db.notifications.insert_one({
        "title": "New member assigned to you.",
        "message": f"Member Name: {member.get('full_name')}, Member ID: {member_id}, Fitness Goal: {fitness_goal}, Assigned: {assignment_date}",
        "trainer_id": trainer["trainer_id"],
        "type": "info",
        "link": f"/trainer/members/{member_id}",
        "is_read": False,
        "created_at": now
    })
    
    # 2. Member receives notification: "Your registration has been approved."
    db.notifications.insert_one({
        "title": "Your registration has been approved.",
        "message": f"Welcome to FITCORE! Your registration for {member.get('plan_name', 'membership')} has been approved.",
        "member_id": member_id,
        "type": "success",
        "link": "/member/dashboard",
        "is_read": False,
        "created_at": now
    })
    
    # 3. Member receives notification: "Your trainer has been assigned."
    db.notifications.insert_one({
        "title": "Your trainer has been assigned.",
        "message": f"Your Trainer: {trainer.get('name')}",
        "member_id": member_id,
        "type": "info",
        "link": "/member/trainer",
        "is_read": False,
        "created_at": now
    })
    
    # Admin system log notification
    log_notification(
        title="Member Request Approved",
        message=f"{member.get('full_name')} ({member_id}) was approved and assigned to trainer {trainer.get('name')}.",
        notif_type="success",
        link=f"/members/{member_id}"
    )
    
    flash(f"Member {member.get('full_name')} approved and assigned to trainer {trainer.get('name')} successfully!", 'success')
    return redirect(url_for('members.member_requests'))

@members_bp.route('/requests/<member_id>/reject', methods=['POST'])
@login_required
def reject_member_request(member_id):
    db = get_db()
    member = db.members.find_one({"member_id": member_id})
    if not member:
        flash("Member request not found.", 'danger')
        return redirect(url_for('members.member_requests'))
        
    rejection_reason = request.form.get('rejection_reason', '').strip() or "Registration information is incomplete."
    now = get_now()
    
    # Store status = 'rejected' and rejection_reason without deleting request
    db.members.update_one(
        {"member_id": member_id},
        {"$set": {
            "status": "rejected",
            "approval_status": "rejected",
            "rejection_reason": rejection_reason,
            "rejected_at": now,
            "updated_at": now
        }}
    )
    
    db.users.update_one(
        {"$or": [{"member_id": member_id}, {"email": member.get("email")}]},
        {"$set": {
            "status": "rejected",
            "rejection_reason": rejection_reason,
            "updated_at": now
        }}
    )
    
    # Member notification: "Your registration request was rejected." and rejection reason
    db.notifications.insert_one({
        "title": "Your registration request was rejected.",
        "message": f"Reason: {rejection_reason}",
        "member_id": member_id,
        "type": "danger",
        "is_read": False,
        "created_at": now
    })
    
    flash(f"Registration request for {member.get('full_name')} was rejected.", 'warning')
    return redirect(url_for('members.member_requests'))

@members_bp.route('/<member_id>/change-trainer', methods=['POST'])
@login_required
def change_trainer(member_id):
    # Security: Changing trainers is restricted exclusively to Admin
    if str(session.get('role', '')).lower() != 'admin':
        flash("Access Denied: Only administrators can change trainer assignments.", 'danger')
        return redirect(url_for('dashboard.index'))
        
    db = get_db()
    member = db.members.find_one({"member_id": member_id})
    if not member:
        flash("Member not found.", 'danger')
        return redirect(url_for('members.list_members'))
        
    new_trainer_id = request.form.get('trainer_id', '').strip()
    now = get_now()
    assignment_date = now.strftime("%d %b %Y")
    
    if new_trainer_id:
        trainer = db.trainers.find_one({"trainer_id": new_trainer_id})
        if not trainer:
            flash("Selected trainer not found.", 'danger')
            return redirect(request.referrer or url_for('members.view_member', member_id=member_id))
            
        trainer_name = trainer.get("name", "Trainer")
        
        # Update Member in database
        db.members.update_one(
            {"member_id": member_id},
            {"$set": {
                "trainer_id": new_trainer_id,
                "trainer_name": trainer_name,
                "updated_at": now
            }}
        )
        
        # Keep Users collection synchronized
        db.users.update_one(
            {"$or": [{"member_id": member_id}, {"email": member.get("email")}]},
            {"$set": {
                "trainer_id": new_trainer_id,
                "trainer_name": trainer_name,
                "updated_at": now
            }}
        )
        
        # 1. Notification to new Trainer
        fitness_goal = member.get('fitness_goal') or 'General Fitness'
        db.notifications.insert_one({
            "title": "New member assigned to you.",
            "message": f"Member Name: {member.get('full_name')}, Member ID: {member_id}, Goal: {fitness_goal}, Assigned: {assignment_date}",
            "trainer_id": new_trainer_id,
            "type": "info",
            "link": f"/trainer/members/{member_id}",
            "is_read": False,
            "created_at": now
        })
        
        # 2. Notification to Member
        db.notifications.insert_one({
            "title": "Your trainer has been assigned.",
            "message": f"Your assigned personal coach has been updated to: {trainer_name}",
            "member_id": member_id,
            "type": "info",
            "link": "/member/trainer",
            "is_read": False,
            "created_at": now
        })
        
        # 3. Log administrative audit notification
        log_notification(
            title="Trainer Assignment Updated",
            message=f"{member.get('full_name')} ({member_id}) was assigned to coach {trainer_name}.",
            notif_type="info",
            link=f"/members/{member_id}"
        )
        
        flash(f"Trainer for {member.get('full_name')} updated to {trainer_name} successfully!", 'success')
    else:
        # Unassign trainer
        db.members.update_one(
            {"member_id": member_id},
            {"$set": {
                "trainer_id": None,
                "trainer_name": None,
                "updated_at": now
            }}
        )
        db.users.update_one(
            {"$or": [{"member_id": member_id}, {"email": member.get("email")}]},
            {"$set": {
                "trainer_id": None,
                "trainer_name": None,
                "updated_at": now
            }}
        )
        
        log_notification(
            title="Trainer Unassigned",
            message=f"Trainer unassigned from {member.get('full_name')} ({member_id}).",
            notif_type="warning",
            link=f"/members/{member_id}"
        )
        
        flash(f"Trainer was unassigned from {member.get('full_name')}.", 'info')
        
    return redirect(request.referrer or url_for('members.view_member', member_id=member_id))

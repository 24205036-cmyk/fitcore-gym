from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import get_db
from utils.decorators import login_required
from utils.ids import get_next_trainer_id, get_next_user_id
from utils.auth import hash_password
from utils.helpers import get_now, format_currency, save_uploaded_file
from utils.validators import validate_trainer_form
from utils.notifier import log_notification

trainers_bp = Blueprint('trainers', __name__, url_prefix='/trainers')

SPECIALIZATIONS = [
    "Weight Training",
    "Cardio",
    "CrossFit",
    "Yoga",
    "Strength Training",
    "Personal Training",
    "Nutrition"
]

@trainers_bp.route('')
@login_required
def list_trainers():
    db = get_db()
    status_filter = request.args.get('status', '').strip()
    spec_filter = request.args.get('specialization', '').strip()
    search_q = request.args.get('search', '').strip()
    
    query = {}
    if status_filter:
        query['status'] = status_filter
    if spec_filter:
        query['specialization'] = spec_filter
    if search_q:
        query['$or'] = [
            {'trainer_id': {'$regex': search_q, '$options': 'i'}},
            {'name': {'$regex': search_q, '$options': 'i'}},
            {'phone': {'$regex': search_q, '$options': 'i'}},
            {'specialization': {'$regex': search_q, '$options': 'i'}}
        ]
        
    trainers = list(db.trainers.find(query).sort("trainer_id", 1))
    
    # Calculate assigned members count for each trainer
    for t in trainers:
        t['assigned_count'] = db.members.count_documents({"trainer_id": t['trainer_id'], "status": "Active"})
        
    total_trainers = len(trainers)
    active_trainers = sum(1 for t in trainers if t.get('status') == 'Active')
    
    # All members list for quick assignment modal
    all_members = list(db.members.find({}, {
        "member_id": 1, "full_name": 1, "trainer_id": 1, "trainer_name": 1, "status": 1, "plan_name": 1
    }).sort("full_name", 1))
    
    return render_template(
        'trainers/list.html',
        trainers=trainers,
        total_trainers=total_trainers,
        active_trainers=active_trainers,
        specializations=SPECIALIZATIONS,
        status_filter=status_filter,
        spec_filter=spec_filter,
        search_q=search_q,
        all_members=all_members
    )

@trainers_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_trainer():
    if request.method == 'POST':
        form = request.form
        is_valid, err_msg = validate_trainer_form(form)
        if not is_valid:
            flash(err_msg, 'danger')
            return render_template('trainers/add.html', form=form, specializations=SPECIALIZATIONS)
            
        photo_path = ""
        if 'profile_photo' in request.files:
            file = request.files['profile_photo']
            if file and file.filename:
                photo_path = save_uploaded_file(file, 'trainers')
                
        trainer_id = get_next_trainer_id()
        salary_val = float(form.get('salary', 0)) if form.get('salary') else 0
        
        new_trainer = {
            "trainer_id": trainer_id,
            "name": form.get('name', '').strip(),
            "photo": photo_path,
            "age": int(form.get('age', 0)) if form.get('age') else None,
            "gender": form.get('gender', 'Male'),
            "phone": form.get('phone', '').strip(),
            "email": form.get('email', '').strip().lower(),
            "specialization": form.get('specialization', '').strip(),
            "experience": form.get('experience', '').strip(),
            "salary": salary_val,
            "joining_date": form.get('joining_date') or get_now().strftime("%Y-%m-%d"),
            "status": form.get('status', 'Active'),
            "created_at": get_now(),
            "updated_at": get_now()
        }
        
        db = get_db()
        db.trainers.insert_one(new_trainer)
        
        # Sync with users collection for Trainer login
        user_id = get_next_user_id()
        db.users.update_one(
            {"$or": [{"email": new_trainer["email"]}, {"trainer_id": trainer_id}]},
            {
                "$setOnInsert": {
                    "user_id": user_id,
                    "trainer_id": trainer_id,
                    "password": hash_password(form.get('password') or "trainer123"),
                    "created_at": get_now()
                },
                "$set": {
                    "name": new_trainer["name"],
                    "email": new_trainer["email"],
                    "phone": new_trainer["phone"],
                    "role": "trainer",
                    "status": "active" if new_trainer["status"] == "Active" else "inactive"
                }
            },
            upsert=True
        )
        
        flash(f"Trainer {new_trainer['name']} ({trainer_id}) added successfully!", 'success')
        return redirect(url_for('trainers.view_trainer', trainer_id=trainer_id))
        
    default_date = get_now().strftime("%Y-%m-%d")
    return render_template('trainers/add.html', specializations=SPECIALIZATIONS, default_date=default_date)

@trainers_bp.route('/<trainer_id>')
@login_required
def view_trainer(trainer_id):
    db = get_db()
    trainer = db.trainers.find_one({"trainer_id": trainer_id})
    if not trainer:
        flash("Trainer not found.", 'danger')
        return redirect(url_for('trainers.list_trainers'))
        
    # Get all assigned members
    assigned_members = list(db.members.find({"trainer_id": trainer_id}))
    active_assigned = sum(1 for m in assigned_members if m.get('status') == 'Active')
    
    # Get all gym members for assignment options
    all_members = list(db.members.find({}, {
        "member_id": 1, "full_name": 1, "trainer_id": 1, "trainer_name": 1, 
        "status": 1, "plan_name": 1, "fitness_goal": 1, "phone": 1
    }).sort("full_name", 1))
    
    unassigned_members = [m for m in all_members if not m.get('trainer_id')]
    other_assigned_members = [m for m in all_members if m.get('trainer_id') and m.get('trainer_id') != trainer_id]
    
    return render_template(
        'trainers/view.html',
        trainer=trainer,
        assigned_members=assigned_members,
        active_assigned=active_assigned,
        total_assigned=len(assigned_members),
        unassigned_members=unassigned_members,
        other_assigned_members=other_assigned_members,
        all_members=all_members,
        salary_formatted=format_currency(trainer.get('salary', 0))
    )

@trainers_bp.route('/<trainer_id>/assign-member', methods=['POST'])
@login_required
def assign_member(trainer_id):
    if str(session.get('role', '')).lower() != 'admin':
        flash("Access Denied: Only administrators can assign members to trainers.", 'danger')
        return redirect(url_for('trainers.view_trainer', trainer_id=trainer_id))

    db = get_db()
    trainer = db.trainers.find_one({"trainer_id": trainer_id})
    if not trainer:
        flash("Trainer not found.", 'danger')
        return redirect(url_for('trainers.list_trainers'))

    member_id = request.form.get('member_id', '').strip()
    if not member_id:
        flash("Please select a member to assign.", 'warning')
        return redirect(url_for('trainers.view_trainer', trainer_id=trainer_id))

    member = db.members.find_one({"member_id": member_id})
    if not member:
        flash("Member not found.", 'danger')
        return redirect(url_for('trainers.view_trainer', trainer_id=trainer_id))

    if member.get('trainer_id') == trainer_id:
        flash(f"{member.get('full_name')} is already assigned to {trainer.get('name')}.", 'info')
        return redirect(url_for('trainers.view_trainer', trainer_id=trainer_id))

    now = get_now()
    assignment_date = now.strftime("%d %b %Y")
    trainer_name = trainer.get('name', 'Trainer')

    # Update member in database
    db.members.update_one(
        {"member_id": member_id},
        {"$set": {
            "trainer_id": trainer_id,
            "trainer_name": trainer_name,
            "updated_at": now
        }}
    )

    # Keep Users collection synchronized
    db.users.update_one(
        {"$or": [{"member_id": member_id}, {"email": member.get("email")}]},
        {"$set": {
            "trainer_id": trainer_id,
            "trainer_name": trainer_name,
            "updated_at": now
        }}
    )

    # 1. Notification to Trainer
    fitness_goal = member.get('fitness_goal') or 'General Fitness'
    db.notifications.insert_one({
        "title": "New member assigned to you.",
        "message": f"Member Name: {member.get('full_name')}, Member ID: {member_id}, Goal: {fitness_goal}, Assigned: {assignment_date}",
        "trainer_id": trainer_id,
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
        link=f"/trainers/{trainer_id}"
    )

    flash(f"Member {member.get('full_name')} ({member_id}) was successfully assigned to coach {trainer_name}!", 'success')
    return redirect(url_for('trainers.view_trainer', trainer_id=trainer_id))

@trainers_bp.route('/<trainer_id>/unassign-member/<member_id>', methods=['POST'])
@login_required
def unassign_member(trainer_id, member_id):
    if str(session.get('role', '')).lower() != 'admin':
        flash("Access Denied: Only administrators can unassign members.", 'danger')
        return redirect(url_for('trainers.view_trainer', trainer_id=trainer_id))

    db = get_db()
    trainer = db.trainers.find_one({"trainer_id": trainer_id})
    member = db.members.find_one({"member_id": member_id})

    if not member:
        flash("Member not found.", 'danger')
        return redirect(url_for('trainers.view_trainer', trainer_id=trainer_id))

    now = get_now()
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

    tr_name = trainer.get('name') if trainer else 'Trainer'
    log_notification(
        title="Trainer Unassigned",
        message=f"{member.get('full_name')} ({member_id}) was removed from coach {tr_name}.",
        notif_type="warning",
        link=f"/trainers/{trainer_id}"
    )

    flash(f"Member {member.get('full_name')} has been unassigned from {tr_name}.", 'info')
    return redirect(url_for('trainers.view_trainer', trainer_id=trainer_id))

@trainers_bp.route('/<trainer_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_trainer(trainer_id):
    db = get_db()
    trainer = db.trainers.find_one({"trainer_id": trainer_id})
    if not trainer:
        flash("Trainer not found.", 'danger')
        return redirect(url_for('trainers.list_trainers'))
        
    if request.method == 'POST':
        form = request.form
        if not form.get('name', '').strip():
            flash("Trainer Name is required.", 'danger')
            return render_template('trainers/edit.html', trainer=trainer, specializations=SPECIALIZATIONS)
            
        update_data = {
            "name": form.get('name', '').strip(),
            "age": int(form.get('age', 0)) if form.get('age') else None,
            "gender": form.get('gender', 'Male'),
            "phone": form.get('phone', '').strip(),
            "email": form.get('email', '').strip().lower(),
            "specialization": form.get('specialization', '').strip(),
            "experience": form.get('experience', '').strip(),
            "salary": float(form.get('salary', 0)) if form.get('salary') else 0,
            "status": form.get('status', 'Active'),
            "updated_at": get_now()
        }
        
        if 'profile_photo' in request.files:
            file = request.files['profile_photo']
            if file and file.filename:
                new_photo = save_uploaded_file(file, 'trainers')
                if new_photo:
                    update_data["photo"] = new_photo
                    
        db.trainers.update_one({"trainer_id": trainer_id}, {"$set": update_data})
        # Also update trainer_name across assigned members
        db.members.update_many({"trainer_id": trainer_id}, {"$set": {"trainer_name": update_data["name"]}})
        
        # Keep users collection synchronized
        tr_status = "active" if update_data.get("status") == "Active" else "inactive"
        db.users.update_one(
            {"trainer_id": trainer_id},
            {
                "$set": {
                    "name": update_data["name"],
                    "email": update_data["email"],
                    "phone": update_data["phone"],
                    "status": tr_status
                }
            }
        )
        
        flash(f"Trainer {update_data['name']} updated successfully.", 'success')
        return redirect(url_for('trainers.view_trainer', trainer_id=trainer_id))
        
    return render_template('trainers/edit.html', trainer=trainer, specializations=SPECIALIZATIONS)

@trainers_bp.route('/<trainer_id>/delete', methods=['POST'])
@login_required
def delete_trainer(trainer_id):
    db = get_db()
    trainer = db.trainers.find_one({"trainer_id": trainer_id})
    if not trainer:
        flash("Trainer not found.", 'danger')
        return redirect(url_for('trainers.list_trainers'))
        
    delete_mode = request.form.get('mode', 'permanent').lower()
    trainer_name = trainer.get('name', 'Trainer')
    
    if delete_mode == 'deactivate':
        # Deactivate only: preserve records and client history
        db.trainers.update_one({"trainer_id": trainer_id}, {"$set": {"status": "Inactive", "updated_at": get_now()}})
        db.users.update_one({"trainer_id": trainer_id}, {"$set": {"status": "inactive"}})
        flash(f"Trainer {trainer_name} ({trainer_id}) was deactivated.", 'warning')
    else:
        # COMPLETE PERMANENT DELETION
        trainer_email = trainer.get("email")
        
        # 1. Delete trainer document
        db.trainers.delete_one({"trainer_id": trainer_id})
        
        # 2. Delete login user account
        user_query = {"$or": [{"trainer_id": trainer_id}]}
        if trainer_email:
            user_query["$or"].append({"email": trainer_email})
        db.users.delete_many(user_query)
        
        # 3. Unlink assigned members so they can be reassigned to other trainers
        db.members.update_many(
            {"trainer_id": trainer_id},
            {"$set": {
                "trainer_id": None,
                "trainer_name": None,
                "updated_at": get_now()
            }}
        )
        
        # 4. Delete schedules for this trainer
        db.schedules.delete_many({"trainer_id": trainer_id})
        
        # 5. Delete workout plans by this trainer
        db.workout_plans.delete_many({"trainer_id": trainer_id})
        
        # 6. Delete trainer notifications
        db.notifications.delete_many({"trainer_id": trainer_id})
        
        # 7. Log administrative audit notification
        log_notification(
            title="Trainer Completely Deleted",
            message=f"{trainer_name} ({trainer_id}) and associated login account were permanently deleted.",
            notif_type="danger",
            link="/trainers"
        )
        
        flash(f"Trainer {trainer_name} ({trainer_id}) and user account were completely deleted from the database.", 'success')
        
    return redirect(url_for('trainers.list_trainers'))

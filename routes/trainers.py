from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import get_db
from utils.decorators import login_required
from utils.ids import get_next_trainer_id
from utils.helpers import get_now, format_currency, save_uploaded_file
from utils.validators import validate_trainer_form

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
    
    return render_template(
        'trainers/list.html',
        trainers=trainers,
        total_trainers=total_trainers,
        active_trainers=active_trainers,
        specializations=SPECIALIZATIONS,
        status_filter=status_filter,
        spec_filter=spec_filter,
        search_q=search_q
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
    
    return render_template(
        'trainers/view.html',
        trainer=trainer,
        assigned_members=assigned_members,
        active_assigned=active_assigned,
        total_assigned=len(assigned_members),
        salary_formatted=format_currency(trainer.get('salary', 0))
    )

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
        
    # Check assigned members
    assigned_count = db.members.count_documents({"trainer_id": trainer_id})
    if assigned_count > 0:
        db.trainers.update_one({"trainer_id": trainer_id}, {"$set": {"status": "Inactive", "updated_at": get_now()}})
        flash(f"Trainer {trainer.get('name')} has {assigned_count} members and was set to Inactive to preserve records.", 'warning')
    else:
        db.trainers.delete_one({"trainer_id": trainer_id})
        flash(f"Trainer {trainer.get('name')} was deleted.", 'info')
        
    return redirect(url_for('trainers.list_trainers'))

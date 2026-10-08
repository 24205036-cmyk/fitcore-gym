from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import get_db
from utils.decorators import login_required
from utils.ids import get_next_plan_id
from utils.helpers import get_now, format_currency
from utils.validators import validate_plan_form

memberships_bp = Blueprint('memberships', __name__, url_prefix='/memberships')

@memberships_bp.route('')
@login_required
def list_plans():
    db = get_db()
    plans = list(db.membership_plans.find().sort("price", 1))
    
    # Enrich each plan with active member count
    for p in plans:
        p['active_members'] = db.members.count_documents({"plan_id": p.get('plan_id'), "status": "Active"})
        p['price_formatted'] = format_currency(p.get('price', 0))
        
    return render_template('memberships/list.html', plans=plans)

@memberships_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_plan():
    if request.method == 'POST':
        form = request.form
        is_valid, err_msg = validate_plan_form(form)
        if not is_valid:
            flash(err_msg, 'danger')
            return render_template('memberships/add.html', form=form)
            
        plan_id = get_next_plan_id()
        new_plan = {
            "plan_id": plan_id,
            "name": form.get('name', '').strip(),
            "duration_days": int(form.get('duration_days', 30)),
            "price": float(form.get('price', 0)),
            "description": form.get('description', '').strip(),
            "status": form.get('status', 'Active'),
            "created_at": get_now(),
            "updated_at": get_now()
        }
        
        db = get_db()
        db.membership_plans.insert_one(new_plan)
        flash(f"Membership Plan '{new_plan['name']}' created successfully!", 'success')
        return redirect(url_for('memberships.list_plans'))
        
    return render_template('memberships/add.html')

@memberships_bp.route('/<plan_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_plan(plan_id):
    db = get_db()
    plan = db.membership_plans.find_one({"plan_id": plan_id})
    if not plan:
        flash("Plan not found.", 'danger')
        return redirect(url_for('memberships.list_plans'))
        
    if request.method == 'POST':
        form = request.form
        is_valid, err_msg = validate_plan_form(form)
        if not is_valid:
            flash(err_msg, 'danger')
            return render_template('memberships/edit.html', plan=plan)
            
        update_data = {
            "name": form.get('name', '').strip(),
            "duration_days": int(form.get('duration_days', 30)),
            "price": float(form.get('price', 0)),
            "description": form.get('description', '').strip(),
            "status": form.get('status', 'Active'),
            "updated_at": get_now()
        }
        
        db.membership_plans.update_one({"plan_id": plan_id}, {"$set": update_data})
        flash(f"Plan '{update_data['name']}' updated successfully.", 'success')
        return redirect(url_for('memberships.list_plans'))
        
    return render_template('memberships/edit.html', plan=plan)

@memberships_bp.route('/<plan_id>/delete', methods=['POST'])
@login_required
def delete_plan(plan_id):
    db = get_db()
    plan = db.membership_plans.find_one({"plan_id": plan_id})
    if not plan:
        flash("Plan not found.", 'danger')
        return redirect(url_for('memberships.list_plans'))
        
    member_count = db.members.count_documents({"plan_id": plan_id})
    if member_count > 0:
        db.membership_plans.update_one({"plan_id": plan_id}, {"$set": {"status": "Inactive", "updated_at": get_now()}})
        flash(f"Plan '{plan.get('name')}' is used by {member_count} members and was set to Inactive instead of deletion.", 'warning')
    else:
        db.membership_plans.delete_one({"plan_id": plan_id})
        flash(f"Plan '{plan.get('name')}' was deleted successfully.", 'info')
        
    return redirect(url_for('memberships.list_plans'))

@memberships_bp.route('/renewals')
@login_required
def list_renewals():
    db = get_db()
    # Find members expiring within next 7 days or recently expired
    now_str = get_now().strftime("%Y-%m-%d")
    members_due = list(db.members.find({
        "status": {"$in": ["Active", "Expired"]}
    }).sort("end_date", 1).limit(50))
    
    return render_template('memberships/renewals.html', members=members_due, today_str=now_str)

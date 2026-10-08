from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime, timedelta
from database import get_db
from utils.decorators import login_required
from utils.ids import get_next_payment_id
from utils.helpers import get_now, format_currency, format_datetime
from utils.validators import validate_payment_form
from utils.notifier import log_notification

payments_bp = Blueprint('payments', __name__, url_prefix='/payments')

PAYMENT_METHODS = ["Cash", "UPI", "Card", "Bank Transfer"]
PAYMENT_STATUSES = ["Paid", "Pending", "Failed"]

@payments_bp.route('')
@login_required
def list_payments():
    db = get_db()
    
    method_filter = request.args.get('method', '').strip()
    status_filter = request.args.get('status', '').strip()
    search_q = request.args.get('search', '').strip()
    period_filter = request.args.get('period', '').strip()
    
    query = {}
    if method_filter:
        query['payment_method'] = method_filter
    if status_filter:
        query['payment_status'] = status_filter
    if search_q:
        query['$or'] = [
            {'payment_id': {'$regex': search_q, '$options': 'i'}},
            {'member_id': {'$regex': search_q, '$options': 'i'}},
            {'member_name': {'$regex': search_q, '$options': 'i'}},
            {'transaction_id': {'$regex': search_q, '$options': 'i'}}
        ]
        
    now = get_now()
    today_str = now.strftime("%Y-%m-%d")
    
    if period_filter == 'today':
        query['payment_date'] = {'$regex': f"^{today_str}"}
    elif period_filter == 'this_month':
        month_str = now.strftime("%Y-%m")
        query['payment_date'] = {'$regex': f"^{month_str}"}
        
    payments = list(db.payments.find(query).sort("payment_date", -1))
    
    # Calculate Revenue Summary Cards (NO CHARTS)
    all_paid_payments = list(db.payments.find({"payment_status": "Paid"}))
    
    total_rev = sum(float(p.get('amount', 0)) for p in all_paid_payments)
    
    # Today's
    today_rev = sum(float(p.get('amount', 0)) for p in all_paid_payments if p.get('payment_date', '').startswith(today_str))
    
    # This Week
    week_start = (now.date() - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
    week_rev = sum(float(p.get('amount', 0)) for p in all_paid_payments if p.get('payment_date', '')[:10] >= week_start)
    
    # This Month
    month_start = now.strftime("%Y-%m")
    month_rev = sum(float(p.get('amount', 0)) for p in all_paid_payments if p.get('payment_date', '').startswith(month_start))
    
    # This Year
    year_start = now.strftime("%Y")
    year_rev = sum(float(p.get('amount', 0)) for p in all_paid_payments if p.get('payment_date', '').startswith(year_start))
    
    # Payment Method Breakdown
    method_stats = {}
    for m in PAYMENT_METHODS:
        m_payments = [p for p in all_paid_payments if p.get('payment_method') == m]
        method_stats[m] = {
            "amount": sum(float(p.get('amount', 0)) for p in m_payments),
            "amount_formatted": format_currency(sum(float(p.get('amount', 0)) for p in m_payments)),
            "count": len(m_payments)
        }
        
    # Payment Status Breakdown
    all_payments = list(db.payments.find({}))
    status_stats = {}
    for s in PAYMENT_STATUSES:
        s_payments = [p for p in all_payments if p.get('payment_status') == s]
        status_stats[s] = {
            "amount": sum(float(p.get('amount', 0)) for p in s_payments),
            "amount_formatted": format_currency(sum(float(p.get('amount', 0)) for p in s_payments)),
            "count": len(s_payments)
        }
        
    return render_template(
        'payments/list.html',
        payments=payments,
        total_revenue=format_currency(total_rev),
        today_revenue=format_currency(today_rev),
        week_revenue=format_currency(week_rev),
        month_revenue=format_currency(month_rev),
        year_revenue=format_currency(year_rev),
        method_stats=method_stats,
        status_stats=status_stats,
        payment_methods=PAYMENT_METHODS,
        payment_statuses=PAYMENT_STATUSES,
        method_filter=method_filter,
        status_filter=status_filter,
        search_q=search_q,
        period_filter=period_filter
    )

@payments_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_payment():
    db = get_db()
    members = list(db.members.find({"status": {"$in": ["Active", "Expired"]}}).sort("full_name", 1))
    
    preselected_member_id = request.args.get('member_id', '')
    
    if request.method == 'POST':
        form = request.form
        is_valid, err_msg = validate_payment_form(form)
        if not is_valid:
            flash(err_msg, 'danger')
            return render_template('payments/add.html', form=form, members=members, methods=PAYMENT_METHODS, statuses=PAYMENT_STATUSES)
            
        member_id = form.get('member_id')
        member = db.members.find_one({"member_id": member_id})
        if not member:
            flash("Selected member does not exist.", 'danger')
            return render_template('payments/add.html', form=form, members=members, methods=PAYMENT_METHODS, statuses=PAYMENT_STATUSES)
            
        pay_id = get_next_payment_id()
        amount_val = float(form.get('amount', 0))
        payment_status = form.get('payment_status', 'Paid')
        
        now_dt = get_now()
        payment_date = form.get('payment_date') or now_dt.strftime("%Y-%m-%d %H:%M:%S")
        
        new_payment = {
            "payment_id": pay_id,
            "member_id": member_id,
            "member_name": member.get('full_name'),
            "plan_id": member.get('plan_id', ''),
            "plan_name": member.get('plan_name', 'General'),
            "amount": amount_val,
            "payment_date": payment_date,
            "payment_method": form.get('payment_method', 'Cash'),
            "transaction_id": form.get('transaction_id', '').strip() or f"TXN-{now_dt.strftime('%Y%m%d%H%M%S')}",
            "payment_status": payment_status,
            "remarks": form.get('remarks', '').strip(),
            "created_at": now_dt
        }
        
        db.payments.insert_one(new_payment)
        
        # Update member payment status
        db.members.update_one({"member_id": member_id}, {"$set": {"payment_status": payment_status, "updated_at": now_dt}})
        
        log_notification(
            title="Payment Received",
            message=f"Received {format_currency(amount_val)} from {member.get('full_name')} via {new_payment['payment_method']}.",
            notif_type="success",
            link="/payments"
        )
        
        flash(f"Payment {pay_id} of {format_currency(amount_val)} recorded successfully for {member.get('full_name')}!", 'success')
        return redirect(url_for('payments.list_payments'))
        
    default_now = get_now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template(
        'payments/add.html',
        members=members,
        methods=PAYMENT_METHODS,
        statuses=PAYMENT_STATUSES,
        preselected_member_id=preselected_member_id,
        default_now=default_now
    )

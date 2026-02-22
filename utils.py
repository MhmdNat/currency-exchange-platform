from model.audit_log import AuditLog, AuditActionType
from flask import request
from flask import abort

from model.transaction import Transaction
from datetime import timezone, datetime, timedelta
from app import db
from model.user import User
from werkzeug.exceptions import HTTPException

#reusable functions


def get_transactions_by_date(startDate, endDate):
    #adding a day to support same day ops
    endDate = endDate + timedelta(days=1)

    # transactions retrieved as lists
    usd_to_lbp_transactions = Transaction.query.filter(
        Transaction.added_date >= startDate,
        Transaction.added_date < endDate,
        Transaction.usd_to_lbp == True).all()
    
    lbp_to_usd_transactions = Transaction.query.filter(
        Transaction.added_date >= startDate,
        Transaction.added_date < endDate,
        Transaction.usd_to_lbp == False).all()
    return (usd_to_lbp_transactions, lbp_to_usd_transactions)


def get_transaction_rates_weighted(usd_to_lbp_transactions, lbp_to_usd_transactions):
    usd_to_lbp_rates = [
        ((t.lbp_amount / t.usd_amount), t.usd_amount) 
        for t in usd_to_lbp_transactions
        if t.usd_amount != 0
    ]
    lbp_to_usd_rates = [
        ((t.lbp_amount / t.usd_amount), t.usd_amount) 
        for t in lbp_to_usd_transactions
        if t.usd_amount !=0
    ]
    return (usd_to_lbp_rates, lbp_to_usd_rates)


def get_weighted_avg_rate(rates_with_weight):
    total_usd=0
    weighted_sum=0
    for r in rates_with_weight:
        #r is tuple rate, usd weight
        rate=r[0]
        usd_weight=r[1]
        total_usd+=usd_weight
        #rate multiplied by its weight
        weighted_sum += rate * usd_weight

    return weighted_sum/total_usd if total_usd != 0 else None

def convert_str_to_time(start_str, end_str):
    #default if parameters not provided correctly
    current_time = datetime.now(timezone.utc)
    three_days_ago = current_time - timedelta(days=3)

    start_time = datetime.fromisoformat(start_str) if start_str else three_days_ago
    end_time = datetime.fromisoformat(end_str) if end_str else current_time

    return start_time, end_time


def extract_timestamps_and_rates(transactions, key_func):
        
        # dictionary where values are lists
        from collections import defaultdict
        grouped = defaultdict(list)
        
        # append the txn to the bucket where hour/day matches and append it to the value list
        for t in transactions:
            grouped[key_func(t)].append(t)
        timestamps = []
        weighted_rates = []

        #sorted keys in increasing order dates
        for ts in sorted(grouped.keys()):
            #transactions of a bucket
            txns = grouped[ts]

            #get rate avg of said bucket
            rates_with_weight = [(t.lbp_amount / t.usd_amount, t.usd_amount) for t in txns]
            weighted_avg = get_weighted_avg_rate(rates_with_weight)

            #append the key
            timestamps.append(str(ts))

            #append the rate
            weighted_rates.append(weighted_avg)
        return timestamps, weighted_rates


def get_current_exchange_rates():
    threeDays = timedelta(days=3)
    currentTime = datetime.now(timezone.utc)
    threeDaysAgo = currentTime - threeDays

    #get transactions by time
    usd_to_lbp_transactions, lbp_to_usd_transactions = get_transactions_by_date(
        threeDaysAgo, 
        currentTime
    )

    # get rates of transactions
    usd_to_lbp_rates_weighted, lbp_to_usd_rates_weighted = get_transaction_rates_weighted(
        usd_to_lbp_transactions,
        lbp_to_usd_transactions
    )

    # final rate of each direction
    avg_weighted_usd_to_lbp_rate = get_weighted_avg_rate(usd_to_lbp_rates_weighted)
    avg_weighted_lbp_to_usd_rate = get_weighted_avg_rate(lbp_to_usd_rates_weighted)

    print(f"current rates: USD to LBP: {avg_weighted_usd_to_lbp_rate}, LBP to USD: {avg_weighted_lbp_to_usd_rate}")
    return {
        "usd_to_lbp": avg_weighted_usd_to_lbp_rate,
        "lbp_to_usd": avg_weighted_lbp_to_usd_rate
    }

def validate_rate_alert_fields(direction, condition, threshold_rate):
    # Validate direction
    allowed_directions = ["BUY_USD", "SELL_USD"]
    if direction not in allowed_directions:
        abort(400, "INVALID direction. Must be BUY_USD or SELL_USD")

    # Validate condition
    if condition not in ["above", "below"]:
        abort(400, "INVALID condition. Must be 'above' or 'below'")

    # Validate threshold_rate
    if not isinstance(threshold_rate, (int, float)) or threshold_rate <= 0:
        abort(400, "INVALID threshold_rate. Must be a positive number")
    return None


def create_audit_log(action_type, description, user_id=None, entity_type=None, entity_id=None, ip_address=None):
    """
    create and commit an audit log entry.
    Automatically fills IP address from request context.
    """
    log = AuditLog(
        action_type=action_type,
        description=description,
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        ip_address=ip_address
    )
    from extensions import db
    db.session.add(log)
    db.session.commit()


def log_preference_change(actor_user_id, actor_role, target_user_id, prefs, ip_address=None):
    """
    Logs a preference change, whether by user or admin.
    actor_user_id: who made the change
    actor_role: role of the actor ("USER" or "ADMIN")
    target_user_id: whose preferences were changed
    prefs: UserPreferences object after change
    ip_address: IP address of the actor
    """
    desc = (
        f"Preferences updated for user_id={target_user_id} by {actor_role} user_id={actor_user_id}. "
        f"New values: default_time_range={prefs.default_time_range}, graph_interval={prefs.graph_interval}"
    )
    create_audit_log(
        action_type=AuditActionType.PREFERENCE_UPDATED,
        description=desc,
        user_id=actor_user_id,
        entity_type="UserPreferences",
        entity_id=prefs.id,
        ip_address=ip_address
    )
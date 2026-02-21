from model.transaction import Transaction
from model.transaction import Transaction
from model.user import User
from extensions import db
from flask import abort, jsonify


def get_transaction_stats():
    total_transactions = Transaction.query.count()
    total_usd_volume = db.session.query(db.func.sum(Transaction.usd_amount)).scalar() or 0
    total_lbp_volume = db.session.query(db.func.sum(Transaction.lbp_amount)).scalar() or 0
    avg_usd_amount = db.session.query(db.func.avg(Transaction.usd_amount)).scalar() or 0
    avg_lbp_amount = db.session.query(db.func.avg(Transaction.lbp_amount)).scalar() or 0
    user_count = User.query.count()
    return {
        'total_transactions': total_transactions,
        'total_usd_volume': total_usd_volume,
        'total_lbp_volume': total_lbp_volume,
        'avg_usd_amount': avg_usd_amount,
        'avg_lbp_amount': avg_lbp_amount,
    }

def change_user_status(user, status=None, role=None):
    if status:
        if status not in ['ACTIVE', 'SUSPENDED', 'BANNED']:
            abort(400, "Invalid status")
        else:
            user.status = status
    if role:
        if role not in ['USER', 'ADMIN']:
            abort(400, "Invalid role")
        else:
            user.role = role
    return user

from flask import Blueprint, request, jsonify
from extensions import db
from jwtAuth import admin_required
from model.transaction import Transaction
from model.offer import Offer
from model.user import User
from sqlalchemy import func
from model.trade import Trade
from datetime import datetime, timedelta, timezone
from utils import convert_str_to_time


analytics_bp = Blueprint('analytics', __name__)


@analytics_bp.route('/admin/analytics/transaction-volume', methods=['GET'])
@admin_required
def get_transaction_volume():
    start_date_str = request.args.get('start-date')
    end_date_str = request.args.get('end-date')
    # Default: last 7 days
    now = datetime.now(timezone.utc)
    if end_date_str:
        try:
            end_date = convert_str_to_time(None, end_date_str)[1]
        except Exception:
            end_date = now
    else:
        end_date = now

    if start_date_str:
        try:
            start_date = convert_str_to_time(start_date_str, None)[0]
        except Exception:
            start_date = end_date - timedelta(days=7)
    else:
        start_date = end_date - timedelta(days=7)
    query = db.session.query(
        #return 0 instead of null if there are no transactions in the period
        func.coalesce(func.sum(Transaction.usd_amount), 0).label('total_usd'),
        func.coalesce(func.sum(Transaction.lbp_amount), 0).label('total_lbp')
    ).filter(Transaction.added_date >= start_date, Transaction.added_date <= end_date)
    result = query.one()
    return jsonify({
        'total_usd': float(result.total_usd),
        'total_lbp': float(result.total_lbp),
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat()
    }), 200


@analytics_bp.route('/admin/analytics/most-active-users', methods=['GET'])
@admin_required
def get_most_active_users():
    #default is 10 but can be set by query parameter
    limit = int(request.args.get('limit', 10))
    if limit < 1:
        return jsonify({'error': 'Limit must be a positive integer'}), 400

    # Count transactions per user
    tx_counts = db.session\
        .query(Transaction.user_id, func.count(Transaction.id)\
                .label('tx_count'))\
                .group_by(Transaction.user_id).all()
    
    # Count trades per user (both maker and taker)
    maker_counts = db.session\
        .query(Trade.maker_id, func.count(Trade.id)\
                .label('trade_count'))\
                .group_by(Trade.maker_id).all()
    taker_counts = db.session\
        .query(Trade.taker_id, func.count(Trade.id)\
                .label('trade_count'))\
                .group_by(Trade.taker_id).all()
    
    user_activity = {}
    #empty dictionary
    #add transaction counts to user activity

    for user_id, tx_count in tx_counts:
        if user_id:
            user_activity[user_id] = user_activity.get(user_id, 0) + tx_count
    #add trade counts to user activity where user is maker 
    for user_id, trade_count in maker_counts:
        if user_id:
            user_activity[user_id] = user_activity.get(user_id, 0) + trade_count
    #ADD trade counts to user activity where user is taker
    for user_id, trade_count in taker_counts:
        if user_id:
            user_activity[user_id] = user_activity.get(user_id, 0) + trade_count
    
    #sort by count in descending order and limit results
    sorted_users = sorted(user_activity.items(), key=lambda x: x[1], reverse=True)[:limit]
    
    #get user names for the sorted user ids
    users = User.query.filter(User.id.in_([u[0] for u in sorted_users])).all()
    
    #create a mapper of user id to user name for easy lookup
    user_mapper = {u.id: u.user_name for u in users}
    
    return jsonify([
        {'user_id': uid, 'user_name': user_mapper.get(uid, ''), 'activity_count': count}
        for uid, count in sorted_users
    ]), 200



@analytics_bp.route('/admin/analytics/marketplace-stats', methods=['GET'])
@admin_required
def get_marketplace_stats():
    #count different offers open partial filled or cancelled
    total_offers = db.session.query(func.count(Offer.id)).scalar()
    # Accepted offers: status is PARTIAL or FILLED
    accepted_offers = db.session.query(func.count(Offer.id)).filter(
        Offer.status.in_(['PARTIAL', 'FILLED'])
    ).scalar()
    canceled_offers = db.session.query(func.count(Offer.id)).filter(Offer.status == 'CANCELLED').scalar()
    return jsonify({
        'total_offers': total_offers,
        'accepted_offers': accepted_offers,
        'canceled_offers': canceled_offers
    }), 200

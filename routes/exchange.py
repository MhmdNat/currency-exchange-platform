from flask import Blueprint, request, jsonify, g
from datetime import datetime, timedelta, timezone
from statistics import pstdev
import jwtAuth  
from model.transaction import Transaction
import utils
from model.userPreferences import UserPreferences
from extensions import limiter

exchange_bp = Blueprint('exchange', __name__)


def _extract_ordered_rates_with_timestamps(transactions):
    """Return chronologically ordered (timestamp_iso, rate) entries."""
    ordered = sorted(transactions, key=lambda t: t.added_date)
    points = []
    for t in ordered:
        if not t.usd_amount:
            continue
        rate = t.lbp_amount / t.usd_amount
        points.append((t.added_date.isoformat(), rate))
    return points


def _calculate_insights(rate_points):
    """Compute trend, volatility, and biggest spike from ordered rate points."""
    if len(rate_points) < 2:
        return {
            "trend": "stable",
            "volatility": "insufficient data",
            "biggest_spike": None,
        }

    rates = [r for _, r in rate_points]
    pct_change = ((rates[-1] - rates[0]) / rates[0] * 100) if rates[0] else 0

    if pct_change > 0.50:
        trend = "up"
    elif pct_change < -0.50:
        trend = "down"
    else:
        trend = "stable"

    returns = []
    biggest_spike = {"timestamp": None, "value": 0.0}
    for idx in range(1, len(rate_points)):
        prev_rate = rate_points[idx - 1][1]
        current_ts, current_rate = rate_points[idx]
        if prev_rate == 0:
            continue

        jump_pct = ((current_rate - prev_rate) / prev_rate) * 100
        returns.append(jump_pct)

        if abs(jump_pct) > abs(biggest_spike["value"]):
            biggest_spike = {
                "timestamp": current_ts,
                "value": jump_pct,
            }

    volatility_value = pstdev(returns) if len(returns) > 1 else 0.0
    if volatility_value < 0.5:
        volatility = "low"
    elif volatility_value < 2:
        volatility = "moderate"
    else:
        volatility = "high"

    return {
        "trend": trend,
        "volatility": volatility,
        "biggest_spike": biggest_spike,
    }

#get exchange rate with rate limiting
@exchange_bp.route('/exchangeRate', methods=['GET'])
@limiter.limit("10 per minute")
def get_exchange_rate():
    # Return weighted exchange rates computed from transactions in the last 72 hours.
    historical_rates = utils.get_current_exchange_rates()
    usd_to_lbp = historical_rates.get("usd_to_lbp")
    lbp_to_usd = historical_rates.get("lbp_to_usd")

    print(f"Retrieved exchange rates: USD to LBP = {usd_to_lbp}, LBP to USD = {lbp_to_usd}")
    return jsonify({
        "message": "Exchange rates retrieved",
        "usd_to_lbp": usd_to_lbp,
        "lbp_to_usd": lbp_to_usd
    }), 200


# get exchange rate with analytics
@exchange_bp.route("/exchangeRate/analytics", methods=["GET"])
@limiter.limit("10 per minute")
def get_exchange_rate_analytics():
    start_str = request.args.get("start")
    end_str = request.args.get("end")

    # Use user preferences for start/end independently
    user_id = jwtAuth.get_auth_user(request)
    #because authentication is optional for this endpoint, 
    # we check if user_id exists before trying to access preferences. 
    # If no user_id and no provided start/end use defaults in conversion function
    if user_id:
        prefs = UserPreferences.query.filter_by(user_id=user_id).first()
        if prefs:
            now = datetime.now(timezone.utc)
            if not start_str:
                if prefs.default_time_range == '1d':
                    start_str = (now - timedelta(days=1)).strftime('%Y-%m-%d') #changes to string for conversion function
                elif prefs.default_time_range == '3d':
                    start_str = (now - timedelta(days=3)).strftime('%Y-%m-%d')
                elif prefs.default_time_range == '1w':
                    start_str = (now - timedelta(weeks=1)).strftime('%Y-%m-%d')
                elif prefs.default_time_range == '1m':
                    start_str = (now - timedelta(days=30)).strftime('%Y-%m-%d')
            if not end_str:
                end_str = now.strftime('%Y-%m-%d')

    #converts to datetime objects, defaults to three days ago and current time
    try:
        start_time, end_time = utils.convert_str_to_time(start_str, end_str)
    except ValueError:
        return jsonify({
        "error": "Invalid date format. Use YYYY-MM-DD"
        }), 400
    
    # get transactions
    usd_to_lbp_transactions, lbp_to_usd_transactions = utils.get_transactions_by_date(
        start_time, end_time
    )

    #get weighted rates
    usd_to_lbp_rates_weighted, lbp_to_usd_rates_weighted = utils.get_transaction_rates_weighted(
        usd_to_lbp_transactions, lbp_to_usd_transactions
    )

    # compute stats for USD to LBP
    usd_rates = [r for r, w in usd_to_lbp_rates_weighted]  # plain rates
    usd_points = _extract_ordered_rates_with_timestamps(usd_to_lbp_transactions)
    usd_stats = {
        "min": min(usd_rates) if usd_rates else None,
        "max": max(usd_rates) if usd_rates else None,
        "weighted_avg": utils.get_weighted_avg_rate(usd_to_lbp_rates_weighted),
        #pct change from first rate to last rate
        "pct_change": ((usd_rates[-1] - usd_rates[0]) / usd_rates[0] * 100) if len(usd_rates) > 1 else 0,
        "insights": _calculate_insights(usd_points),
    }

    # compute stats for LBP to USD
    lbp_rates = [r for r, w in lbp_to_usd_rates_weighted] #plain rates
    lbp_points = _extract_ordered_rates_with_timestamps(lbp_to_usd_transactions)
    lbp_stats = {
        "min": min(lbp_rates) if lbp_rates else None,
        "max": max(lbp_rates) if lbp_rates else None,
        "weighted_avg": utils.get_weighted_avg_rate(lbp_to_usd_rates_weighted),
        "pct_change": ((lbp_rates[-1] - lbp_rates[0]) / lbp_rates[0] * 100) if len(lbp_rates) > 1 else 0,
        "insights": _calculate_insights(lbp_points),
    }

    return jsonify({
        "message": "Exchange rate analytics retrieved",
        "usd_to_lbp": usd_stats,
        "lbp_to_usd": lbp_stats
    }), 200


# FEATURE 2
#Exchange Rate History Graph Support (Time-Series Data)

@exchange_bp.route("/exchangeRate/history", methods=["GET"])
@limiter.limit("10 per minute")
#get transactions created by authenticated user
def get_exchange_rate_history():

    #returns lists of rates per interval
    start_str = request.args.get("start")
    end_str = request.args.get("end")
    interval = request.args.get("interval") # if user provides interval use it, otherwise use preference

    # Use user preferences if not provided
    user_id = jwtAuth.get_auth_user(request)
    if user_id:
        prefs = UserPreferences.query.filter_by(user_id=user_id).first()
        if prefs:
            if not start_str:
                now = datetime.now(timezone.utc)
                if prefs.default_time_range == '1d':
                    start_str = (now - timedelta(days=1)).strftime('%Y-%m-%d')
                elif prefs.default_time_range == '3d':
                    start_str = (now - timedelta(days=3)).strftime('%Y-%m-%d')
                elif prefs.default_time_range == '1w':
                    start_str = (now - timedelta(weeks=1)).strftime('%Y-%m-%d')
                elif prefs.default_time_range == '1m':
                    start_str = (now - timedelta(days=30)).strftime('%Y-%m-%d')
                end_str = now.strftime('%Y-%m-%d')
            if not interval:
                interval = prefs.graph_interval
            if not end_str:
                end_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')       
    print(f"Received request for exchange rate history with start={start_str}, end={end_str}, interval={interval}")
    #converts to datetime objects, defaults to three days ago and current time
    try:
        start_time, end_time = utils.convert_str_to_time(start_str, end_str)
    except ValueError:
        return jsonify({
        "error": "Invalid date format. Use YYYY-MM-DD"
        }), 400
    
    usd_txns, lbp_txns = utils.get_transactions_by_date(start_time, end_time)

    # group transactions by interval
    if interval == "hourly":
        func = lambda t: t.added_date.replace(minute=0, second=0, microsecond=0) # keep day but round hour down
        
    else:  # daily
        func = lambda t: t.added_date.date()

    usd_timestamps, usd_rates = utils.extract_timestamps_and_rates(usd_txns, func)
    lbp_timestamps, lbp_rates = utils.extract_timestamps_and_rates(lbp_txns, func)

    return jsonify({
        "usd_to_lbp": {
            "timestamps": usd_timestamps, 
            "rates": usd_rates
            },
        "lbp_to_usd": {
            "timestamps": lbp_timestamps, 
            "rates": lbp_rates
            },
    }), 200

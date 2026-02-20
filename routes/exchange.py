from flask import Blueprint, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime, timedelta, timezone
from model.transaction import Transaction
import utils

exchange_bp = Blueprint('exchange', __name__)
limiter = Limiter(key_func=get_remote_address)

#get exchange rate with rate limiting
@exchange_bp.route('/exchangeRate', methods=['GET'])
@limiter.limit("10 per minute")
def get_exchange_rate():
    threeDays = timedelta(days=3)
    currentTime = datetime.now(timezone.utc)
    threeDaysAgo = currentTime - threeDays

    #get transactions by time
    usd_to_lbp_transactions, lbp_to_usd_transactions = utils.get_transactions_by_date(
        threeDaysAgo, 
        currentTime
    )

    # get rates of transactions
    usd_to_lbp_rates_weighted, lbp_to_usd_rates_weighted = utils.get_transaction_rates_weighted(
        usd_to_lbp_transactions,
        lbp_to_usd_transactions
    )

    # final rate of each direction
    avg_weighted_usd_to_lbp_rate = utils.get_weighted_avg_rate(usd_to_lbp_rates_weighted)
    avg_weighted_lbp_to_usd_rate = utils.get_weighted_avg_rate(lbp_to_usd_rates_weighted)

    return jsonify({
        "message":"Retrieved average exchange rates",
        "usd_to_lbp":avg_weighted_usd_to_lbp_rate,
        "lbp_to_usd":avg_weighted_lbp_to_usd_rate
    }), 200


# get exchange rate with analytics
@exchange_bp.route("/exchangeRate/analytics", methods=["GET"])
@limiter.limit("10 per minute")
def get_exchange_rate_analytics():
    start_str = request.args.get("start") #this would be "2026-02-16"
    end_str = request.args.get("end")

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
    usd_stats = {
        "min": min(usd_rates) if usd_rates else None,
        "max": max(usd_rates) if usd_rates else None,
        "weighted_avg": utils.get_weighted_avg_rate(usd_to_lbp_rates_weighted),
        #pct change from first rate to last rate
        "pct_change": ((usd_rates[-1] - usd_rates[0]) / usd_rates[0] * 100) if len(usd_rates) > 1 else 0
    }

    # compute stats for LBP to USD
    lbp_rates = [r for r, w in lbp_to_usd_rates_weighted] #plain rates
    lbp_stats = {
        "min": min(lbp_rates) if lbp_rates else None,
        "max": max(lbp_rates) if lbp_rates else None,
        "weighted_avg": utils.get_weighted_avg_rate(lbp_to_usd_rates_weighted),
        "pct_change": ((lbp_rates[-1] - lbp_rates[0]) / lbp_rates[0] * 100) if len(lbp_rates) > 1 else 0
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
    interval = request.args.get("interval", "daily") #default is daily

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
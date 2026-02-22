from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from jwtAuth import admin_required 
from model.exchange_rate import ExchangeRate, ExchangeRateSchema
from services.rate_service import RateService  # service handling rate logic
from utils import convert_str_to_time 
from flask import abort

# Blueprint for admin endpoints related to rate quality
rate_quality_bp = Blueprint("rate_quality", __name__)
rate_schema = ExchangeRateSchema()
rates_schema = ExchangeRateSchema(many=True)


def serialize_rate(rate):
    """
    Convert ExchangeRate object to a JSON-serializable dictionary
    Includes flag and anomaly info
    """
    return rate_schema.dump(rate)



@rate_quality_bp.route("/admin/rates", methods=["POST"])
@admin_required 
def create_rate():
    """
    Create a new exchange rate
    Validates input, checks for anomalies, and saves to DB
    """
    payload = request.get_json()
    base_currency = payload.get("base_currency")
    quote_currency = payload.get("quote_currency")
    rate_value = payload.get("rate_value")
    source = payload.get("source")

    # use the service to validate, flag, and save the rate
    rate = RateService.save_rate_if_valid(
        base_currency=base_currency,
        quote_currency=quote_currency,
        rate_value=rate_value,
        source=source,
    )
    return jsonify({"rate": rate_schema.dump(rate)}), 201  # HTTP 201 = Created


@rate_quality_bp.route("/admin/rates", methods=["GET"])
@admin_required
def get_latest_rates():
    """
    Get the latest rate for each currency pair
    Uses the service to fetch the most recent rates only
    """
    latest_rates = RateService.get_latest_rates_by_pair()
    response_rates = [
        {
            "direction": item["direction"],
            "rate": rate_schema.dump(item["rate"])
        }
        for item in latest_rates
    ]
    return jsonify({"rates": response_rates}), 200


@rate_quality_bp.route("/admin/rates/anomalies", methods=["GET"])
@admin_required
def get_anomalous_rates():
    """
    Get all flagged (anomalous) rates
    Optional query parameters:
      start_date = ISO datetime string to filter rates after this timestamp
      end_date = ISO datetime string to filter rates before this timestamp
    Returns rates ordered from newest to oldest
    """
    start_value = request.args.get("start_date")
    end_value = request.args.get("end_date")

    # start with all flagged rates
    query = ExchangeRate.query.filter_by(is_flagged=True)

    # filter by start_date if provided
    if start_value:
        try:
            parsed_start, _ = convert_str_to_time(start_value, start_value)
        except (ValueError, TypeError):
            abort(400, "Invalid start_date. Use ISO format.")
        query = query.filter(ExchangeRate.created_at >= parsed_start)

    # filter by end_date if provided
    if end_value:
        try:
            parsed_end, _ = convert_str_to_time(end_value, end_value)
        except (ValueError, TypeError):
            abort(400, "Invalid end_date. Use ISO format.")
        query = query.filter(ExchangeRate.created_at <= parsed_end)

    # order results newest first
    anomalies = query.order_by(ExchangeRate.created_at.desc(), ExchangeRate.id.desc()).all()

    # serialize each anomaly rate to JSON
    return jsonify({"anomalies": rates_schema.dump(anomalies)}), 200

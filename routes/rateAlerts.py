from flask import Blueprint, request, jsonify, abort, g
from model.rateAlerts import RateAlert, RateAlertSchema
from model.watchlist import WatchlistItem
from jwtAuth import jwt_required
from extensions import db
from utils import validate_rate_alert_fields

rateAlerts_bp = Blueprint('rateAlerts', __name__)

rateAlert_schema = RateAlertSchema()
rateAlerts_schema = RateAlertSchema(many=True)

# Create alert endpoint
@rateAlerts_bp.route("/rateAlerts", methods=["POST"])
@jwt_required
def create_rate_alert():
    data = request.json
    if not data:
        abort(400, "INVALID JSON PAYLOAD")

    user_id = g.current_user_id

    # Required fields
    required_fields = ["direction", "threshold_rate", "condition"]

    for field in required_fields:
        if field not in data:
            abort(400, f"MISSING FIELD: {field}")

    direction = data.get("direction").upper()
    threshold_rate = data.get("threshold_rate")
    condition = data.get("condition").lower()
    # validates the fields and raises an HTTPException with a 400 status code and error message if any field is invalid
    validate_rate_alert_fields(direction, condition, threshold_rate)

    # Create the alert
    new_alert = RateAlert(
        user_id=user_id,
        direction=direction,
        threshold_rate=threshold_rate,
        condition=condition
    )

    db.session.add(new_alert)
    db.session.commit()

    return rateAlert_schema.jsonify(new_alert), 201

# View my alerts endpoint
@rateAlerts_bp.route("/rateAlerts", methods=["GET"])
@jwt_required
def get_my_rate_alerts():
    user_id = g.current_user_id
    alerts = RateAlert.query.filter_by(user_id=user_id).all()
    return rateAlerts_schema.jsonify(alerts), 200

# Delete alert endpoint
@rateAlerts_bp.route("/rateAlerts/<int:alert_id>", methods=["DELETE"])
@jwt_required
def delete_rate_alert(alert_id):
    user_id = g.current_user_id
    alert = RateAlert.query.filter_by(id=alert_id).first()

    if not alert:
        abort(404, "Alert not found")

    if alert.user_id != user_id:
        abort(403, "You can only delete your own alerts")

    # Delete all watchlist items linked to this alert
    watchlist_items = WatchlistItem.query.filter_by(rate_alert_id=alert_id).all()
    for item in watchlist_items:
        db.session.delete(item)
    db.session.commit()  # Commit after deleting watchlist items

    db.session.delete(alert)
    db.session.commit()

    return '', 204
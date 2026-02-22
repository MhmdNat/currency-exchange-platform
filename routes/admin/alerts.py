from flask import request, jsonify, abort
from extensions import db
from routes.admin.bp import admin_bp
from model.user import User
from model.rateAlerts import RateAlert, RateAlertSchema
from utils import validate_rate_alert_fields

rateAlert_schema = RateAlertSchema()

@admin_bp.route('/admin/user/<int:user_id>/alerts/', methods=['POST'])
def create_user_alert(user_id):
    user = User.query.get(user_id)
    if not user:
        abort(404, f"User with id {user_id} not found")
    data = request.json
    if not data:
        abort(400, "INVALID JSON PAYLOAD")
    required_fields = ["direction", "threshold_rate", "condition"]
    for field in required_fields:
        if field not in data:
            abort(400, f"MISSING FIELD: {field}")
    direction = data.get("direction").upper()
    threshold_rate = data.get("threshold_rate")
    condition = data.get("condition").lower()
    validate_rate_alert_fields(direction, condition, threshold_rate)
    new_alert = RateAlert(
        user_id=user_id,
        direction=direction,
        threshold_rate=threshold_rate,
        condition=condition
    )
    db.session.add(new_alert)
    db.session.commit()
    return rateAlert_schema.jsonify(new_alert), 201

@admin_bp.route('/admin/user/<int:user_id>/alerts/<int:alert_id>', methods=['PUT'])
def update_user_alert(user_id, alert_id):
    data = request.json
    if not data:
        abort(400, "INVALID JSON PAYLOAD")
    alert = RateAlert.query.filter_by(id=alert_id).first()
    if not alert:
        abort(404, "Alert not found")
    if alert.user_id != user_id:
        abort(403, f"User {user_id} does not own this alert {alert_id} and cannot update it")
    direction = data.get("direction", alert.direction).upper()
    threshold_rate = data.get("threshold_rate", alert.threshold_rate)
    condition = data.get("condition", alert.condition).lower()
    validate_rate_alert_fields(direction, condition, threshold_rate)
    alert.direction = direction
    alert.threshold_rate = threshold_rate
    alert.condition = condition
    db.session.commit()
    return rateAlert_schema.jsonify(alert), 200

@admin_bp.route('/admin/user/<int:user_id>/alerts/<int:alert_id>', methods=['DELETE'])
def delete_user_alerts(user_id, alert_id):
    user = User.query.get(user_id)
    if not user:
        abort(404, f"User with id {user_id} not found")
    alert = RateAlert.query.filter_by(id=alert_id).first()
    if not alert:
        abort(404, "Alert not found")
    if alert.user_id != user_id:
        abort(403, f"User {user_id} does not own this alert {alert_id} and cannot delete it")
    db.session.delete(alert)
    db.session.commit()
    return '', 204

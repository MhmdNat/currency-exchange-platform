from flask import abort, request, jsonify
from jwtAuth import admin_required
from model.user import User, UserSchema
from model.transaction import Transaction
from model.userPreferences import UserPreferences, UserPreferencesSchema
from model.rateAlerts import RateAlert, RateAlertSchema
from model.watchlist import WatchlistItem
from extensions import db
from flask import Blueprint
from utils import validate_rate_alert_fields
from routes.admin.utils import get_transaction_stats, change_user_status 



admin_bp = Blueprint('admin', __name__)
user_schema = UserSchema()
preferences_schema = UserPreferencesSchema()
rateAlert_schema = RateAlertSchema()


@admin_bp.route('/admin/users', methods=['GET'])
@admin_required
def view_all_users():
    users = User.query.all()
    #return json of all users with their id, username, and status (ACTIVE, SUSPENDED, BANNED)
    return jsonify([user_schema.dump(user) for user in users]), 200


@admin_bp.route('/admin/transaction-stats', methods=['GET'])
@admin_required
def view_transaction_stats():
    stats = get_transaction_stats()
    return jsonify(stats)


@admin_bp.route('/admin/user/<int:user_id>/status', methods=['PUT'])
@admin_required
def manage_user_status(user_id):
    data = request.json
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    status = data.get('status')
    role = data.get('role')
    #if field provided validate and update, if not its ignored and remains unchanged
    user = change_user_status(user, status=status, role=role)
    db.session.commit()
    return jsonify(user_schema.dump(user)), 200

@admin_bp.route('/admin/user/<int:user_id>/preferences', methods=['POST', 'DELETE'])
@admin_required
def manage_user_preferences(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    if request.method == 'POST':
        # Create preferences
        data = request.json
        prefs = UserPreferences.query.filter_by(user_id=user_id).first()
        if not prefs:
            #create new preferences if they don't exist, otherwise update existing preferences
            prefs = UserPreferences(user_id=user_id)
            db.session.add(prefs)
        #update preferences based on provided data, if a field is not provided or invalid it will remain unchanged
        if 'default_time_range' in data and data['default_time_range'] in ['1d', '3d', '1w', '1m']:
            prefs.default_time_range = data['default_time_range']
        if 'graph_interval' in data and data['graph_interval'] in ['hourly', 'daily']:
            prefs.graph_interval = data['graph_interval']
        db.session.commit()
        return jsonify({
            'message': 'Preferences created',
            'preferences': preferences_schema.dump(prefs)
                        }), 200
    
    elif request.method == 'DELETE':
        prefs = user.preferences
        if not prefs:
            return jsonify({'error': 'Preferences not found'}), 404
        db.session.add(prefs)
        prefs.user_id = user_id 
        prefs.default_time_range = '3d' #reset to default values
        prefs.graph_interval = 'daily' #reset to default values
        db.session.commit()
        return "", 204
    

@admin_bp.route('/admin/user/<int:user_id>/alerts/', methods=['POST'])  
@admin_required
def create_user_alert(user_id):
    user = User.query.get(user_id)
    if not user:
        abort(404, f"User with id {user_id} not found")
    data = request.json
    if not data:
        abort(400, "INVALID JSON PAYLOAD")
    # Required fields
    required_fields = ["direction", "threshold_rate", "condition"]

    for field in required_fields:
        if field not in data:
            abort(400, f"MISSING FIELD: {field}")

    direction = data.get("direction").upper()
    threshold_rate = data.get("threshold_rate")
    condition = data.get("condition").lower()

    #here we can reuse the same validation function we use for regular users since the fields are the same, 
    # if any field is invalid it will raise an HTTPException with a 400 status code and error message
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

@admin_bp.route('/admin/user/<int:user_id>/alerts/<int:alert_id>', methods=['PUT'])    
@admin_required
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
@admin_required
def delete_user_alerts(user_id, alert_id):
    user = User.query.get(user_id)
    if not user:
        abort(404, f"User with id {user_id} not found")
    alert = RateAlert.query.filter_by(id=alert_id).first()

    if not alert:
        abort(404, "Alert not found")

    if alert.user_id != user_id:
        abort(403, f"User {user_id} does not own this alert {alert_id} and cannot delete it")

    # Delete all watchlist items linked to this alert
    
    watchlist_items = WatchlistItem.query.filter_by(rate_alert_id=alert_id).all()
    for item in watchlist_items:
        db.session.delete(item)
    db.session.commit()  # Commit after deleting watchlist items

    db.session.delete(alert)
    db.session.commit()
    return '', 204

    
@admin_bp.route('/admin/user/<int:user_id>/status', methods=['PUT'])
@admin_required
def set_user_status(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    data = request.json
    status = data.get('status')
    if status not in ['ACTIVE', 'SUSPENDED', 'BANNED']:
        return jsonify({'error': 'Invalid status'}), 400
    user.status = status
    db.session.commit()
    return jsonify(user_schema.dump(user)), 200
from flask import Blueprint, request, jsonify, g
from extensions import db
from model.user import User
from model.userPreferences import UserPreferences, UserPreferencesSchema
from utils import log_preference_change
from jwtAuth import jwt_required
from model.audit_log import AuditLog, AuditLogSchema    

preferences_bp = Blueprint('preferences', __name__)
preference_schema = UserPreferencesSchema()
audit_logs_schema = AuditLogSchema() 

@preferences_bp.route('/preferences', methods=['GET'])
@jwt_required
def get_preferences():
    user_id = g.current_user_id
    prefs = UserPreferences.query.filter_by(user_id=user_id).first()
    if prefs:
        return jsonify({
            'default_time_range': prefs.default_time_range,
            'graph_interval': prefs.graph_interval
        }), 200
    else:
        return jsonify({'message': 'No preferences found', 'default_time_range': '3d', 'graph_interval': 'daily'}), 200

@preferences_bp.route('/preferences', methods=['POST'])
@jwt_required
def set_preferences():
    user_id = g.current_user_id
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
    # Audit log for preference updateuser
    actor_user = User.query.get(user_id)
    log_preference_change(
        actor_user_id=user_id,
        actor_role="USER",
        target_user_id=user_id,
        prefs=prefs,
        ip_address=request.remote_addr
    )
    return jsonify({
        'message': 'Preferences updated',
        'preferences': preference_schema.dump(prefs)
    }), 200


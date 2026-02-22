from flask import request, jsonify, g
from extensions import db
from routes.admin.bp import admin_bp
from model.user import User
from model.userPreferences import UserPreferences, UserPreferencesSchema
from utils import log_preference_change

preferences_schema = UserPreferencesSchema()

@admin_bp.route('/admin/user/<int:user_id>/preferences', methods=['POST', 'DELETE'])
def manage_user_preferences(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    if request.method == 'POST':
        data = request.json
        prefs = UserPreferences.query.filter_by(user_id=user_id).first()
        if not prefs:
            prefs = UserPreferences(user_id=user_id)
            db.session.add(prefs)
        if 'default_time_range' in data and data['default_time_range'] in ['1d', '3d', '1w', '1m']:
            prefs.default_time_range = data['default_time_range']
        if 'graph_interval' in data and data['graph_interval'] in ['hourly', 'daily']:
            prefs.graph_interval = data['graph_interval']
        db.session.commit()
        actor_user_id = getattr(g, 'current_user_id', None)
        log_preference_change(
            actor_user_id=actor_user_id,
            actor_role="ADMIN",
            target_user_id=user_id,
            prefs=prefs,
            ip_address=request.remote_addr
        )
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
        prefs.default_time_range = '3d'
        prefs.graph_interval = 'daily'
        db.session.commit()
        return '', 204

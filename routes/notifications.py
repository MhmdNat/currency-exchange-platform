from flask import Blueprint, jsonify, request, g, abort
from jwtAuth import jwt_required
from model.notifications import Notification
from extensions import db

notifications_bp = Blueprint('notifications', __name__)

@notifications_bp.route('/notifications', methods=['GET'])
@jwt_required
def get_notifications():
    user_id = g.current_user_id
    notifications = Notification.query.filter_by(user_id=user_id).order_by(Notification.created_at.desc()).all()
    return jsonify([
        {
            'id': n.id,
            'message': n.message,
            'created_at': n.created_at.isoformat(),
            'read': n.read,
            'type': n.type
        } for n in notifications
    ]), 200

@notifications_bp.route('/notifications/<int:notification_id>/read', methods=['PATCH'])
@jwt_required
def mark_notification_read(notification_id):
    user_id = g.current_user_id
    notification = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
    if not notification:
        abort(404, 'Notification not found')
    notification.read = True
    db.session.commit()
    return jsonify({'message': 'Notification marked as read'}), 200

@notifications_bp.route('/notifications/<int:notification_id>', methods=['DELETE'])
@jwt_required
def delete_notification(notification_id):
    user_id = g.current_user_id
    notification = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
    if not notification:
        abort(404, 'Notification not found')
    db.session.delete(notification)
    db.session.commit()
    return jsonify({'message': 'Notification deleted'}), 200

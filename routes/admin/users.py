from model.user import User, UserSchema
from extensions import db
from routes.admin.bp import admin_bp
from flask import request, jsonify, abort

user_schema = UserSchema()

@admin_bp.route('/admin/users', methods=['GET'])
def view_all_users():
    users = User.query.all()
    return jsonify([user_schema.dump(user) for user in users]), 200

@admin_bp.route('/admin/user/<int:user_id>/status', methods=['PUT'])
def manage_user_status(user_id):
    data = request.json
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    status = data.get('status')
    role = data.get('role')
    user.status = status if status else user.status
    user.role = role if role else user.role
    db.session.commit()
    return jsonify(user_schema.dump(user)), 200

@admin_bp.route('/admin/user/<int:user_id>/status', methods=['PUT'])
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

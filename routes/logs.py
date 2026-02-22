
from jwtAuth import jwt_required
from model.audit_log import AuditLog, AuditLogSchema
from flask import Blueprint, jsonify, g

logs_bp = Blueprint('logs', __name__)
audit_logs_schema = AuditLogSchema()
@logs_bp.route('/audit-logs', methods=['GET'])
@jwt_required
def view_my_audit_logs():
    user_id = g.current_user_id
    logs = AuditLog.query.filter_by(user_id=user_id).order_by(AuditLog.timestamp.desc()).all()
    return jsonify(audit_logs_schema.dump(logs)), 200
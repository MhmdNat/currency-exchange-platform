from routes.admin.bp import admin_bp
from model.audit_log import AuditLog, AuditLogSchema
from flask import jsonify

audit_logs_schema = AuditLogSchema()
@admin_bp.route('/admin/audit-logs', methods=['GET'])
def view_all_audit_logs():
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).all()
    return jsonify(audit_logs_schema.dump(logs)), 200

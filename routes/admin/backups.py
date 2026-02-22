from flask import Blueprint, request, jsonify

from extensions import db
from jwtAuth import admin_required
from services.backup_service import BackupService


backups_bp = Blueprint("backups", __name__)


@backups_bp.route('/admin/backup', methods=['POST'])
@admin_required
def trigger_manual_backup():
    try:
        status = BackupService.create_backup(trigger="manual")
        return jsonify({
            "message": "Backup completed",
            "backup": status
        }), 201
    except Exception as exc:
        return jsonify({"error": f"Backup failed: {str(exc)}"}), 500


@backups_bp.route('/admin/backup/restore', methods=['POST'])
@admin_required
def restore_backup():
    data = request.json or {}
    backup_id = data.get("backup_id")
    try:
        result = BackupService.restore_backup(backup_id=backup_id)
        return jsonify({
            "message": "Restore completed",
            "restore": result
        }), 200
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:
        db.session.rollback()
        return jsonify({"error": f"Restore failed: {str(exc)}"}), 500


@backups_bp.route('/admin/backup/status', methods=['GET'])
@admin_required
def get_backup_status():
    status = BackupService.get_status()
    return jsonify(status), 200

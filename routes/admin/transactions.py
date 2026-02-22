from extensions import db
from routes.admin.bp import admin_bp
from model.transaction import Transaction
from utils import get_transaction_stats
from flask import jsonify

@admin_bp.route('/admin/transaction-stats', methods=['GET'])
def view_transaction_stats():
    stats = get_transaction_stats()
    return jsonify(stats)

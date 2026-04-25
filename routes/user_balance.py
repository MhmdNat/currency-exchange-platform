from flask import Blueprint, jsonify, g
from jwtAuth import jwt_required
from model.userBalance import UserBalance
from extensions import limiter


user_balance_bp = Blueprint("user_balance", __name__)


@user_balance_bp.route("/balance", methods=["GET"])
@limiter.limit("20 per minute")
@jwt_required
def get_user_balance():
    user_id = g.current_user_id

    user_balance = UserBalance.query.filter_by(user_id=user_id).first()
    if not user_balance:
        return jsonify({"error": "User balance not found"}), 404

    return jsonify(
        {
            "usd_balance": user_balance.usd_amount,
            "lbp_balance": user_balance.lbp_amount,
        }
    ), 200

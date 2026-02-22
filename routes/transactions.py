from flask import Blueprint, request, jsonify, abort
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from model.transaction import Transaction, TransactionSchema, db
from model.audit_log import AuditLog, AuditActionType
import jwtAuth
from datetime import datetime, timedelta, timezone
from jwt import ExpiredSignatureError, InvalidTokenError
from utils import create_audit_log


transactions_bp = Blueprint('transactions', __name__)
limiter = Limiter(key_func=get_remote_address)

transaction_schema = TransactionSchema()
transactions_schema = TransactionSchema(many=True)

@transactions_bp.route("/transaction", methods=["GET"])
@limiter.limit("10 per minute")
def get_user_transactions():
    try:
        user_id = jwtAuth.get_auth_user(request)
    except InvalidTokenError as e:
        abort(401, e)
    except  ExpiredSignatureError as e:
        abort(401, e)
    if not user_id:
        abort(401, "error: Unauthorized user")
    
    #here the user is authenticated
    transactions=db.session.execute(
        db.select(Transaction).where(Transaction.user_id==user_id)
    ).scalars().all()

    return jsonify({
        "message":"Retrieved user's transactions",
        "transactions":transactions_schema.dump(transactions)
    }), 200


#create transaction with rate limiter
@transactions_bp.route('/transaction', methods=['POST'])
@limiter.limit("10 per minute")
def add_transaction():
    data = request.json

    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400
    
    usd_amount = data.get("usd_amount", 0)
    lbp_amount = data.get("lbp_amount", 0)
    usd_to_lbp = data.get("usd_to_lbp")

    #either user id if authenticated or none 
    try:
        user_id = jwtAuth.get_auth_user(request)
    except InvalidTokenError as e:
        user_id = None
    except  ExpiredSignatureError as e:
        user_id = None


    #if not an instance of boolean return error
    if not isinstance(usd_to_lbp, bool):
        return jsonify({"error":"Direction must be boolean"}), 400

    #validating currency types and returning error if invalid
    try:
        usd_amount=float(usd_amount)
        lbp_amount=float(lbp_amount)

    except (ValueError, TypeError):
        return jsonify({"error":"Amounts must be numbers"}), 400

    # correct types need to validate values
    if (
        usd_amount<=0 or
        lbp_amount<=0
        ):
        return jsonify({"error":"Invalid amount"}), 400

    #input has been validated, create transaction instance
    t = Transaction(
        usd_amount=usd_amount,
        lbp_amount=lbp_amount,
        usd_to_lbp=usd_to_lbp,
        user_id=user_id,
    )
    db.session.add(t)
    db.session.commit()


    create_audit_log(
        action_type=AuditActionType.TRANSACTION_CREATED,
        description=f"Transaction created: USD {usd_amount}, LBP {lbp_amount}, Direction: {'USD to LBP' if usd_to_lbp else 'LBP to USD'}.",
        user_id=user_id,
        entity_type="Transaction",
        entity_id=t.id,
        ip_address=request.remote_addr
    )

    return jsonify(
        {
            "message": "Transaction created successfully",
            "transaction": transaction_schema.dump(t),
        }
    ), 201
from flask import Blueprint, request, jsonify, g
from model.transaction import Transaction, TransactionSchema, db
from model.userBalance import UserBalance
from model.audit_log import AuditLog, AuditActionType
from services.rate_service import RateService
import jwtAuth
from jwtAuth import jwt_required
from datetime import datetime, timedelta, timezone
from jwt import ExpiredSignatureError, InvalidTokenError
from werkzeug.exceptions import HTTPException
from utils import create_audit_log, create_notification
from extensions import limiter, critical_rate_limit


transactions_bp = Blueprint('transactions', __name__)

transaction_schema = TransactionSchema()
transactions_schema = TransactionSchema(many=True)


def _json_error(message, status_code):
    return jsonify({"error": message}), status_code

@transactions_bp.route("/transaction", methods=["GET"])
@limiter.limit("10 per minute")
@jwt_required
def get_user_transactions():
    user_id = g.current_user_id

    transactions=db.session.execute(
        db.select(Transaction).where(Transaction.user_id==user_id)
    ).scalars().all()

    return jsonify({
        "message":"Retrieved user's transactions",
        "transactions":transactions_schema.dump(transactions)
    }), 200


#create transaction with rate limiter
@transactions_bp.route('/transaction', methods=['POST'])
@transactions_bp.route('/transactions', methods=['POST'])
@critical_rate_limit
@jwt_required
def add_transaction():
    data = request.json

    if not data:
        return _json_error("Invalid JSON payload", 400)
    
    usd_amount = data.get("usd_amount", 0)
    lbp_amount = data.get("lbp_amount", 0)
    usd_to_lbp = data.get("usd_to_lbp")

    user_id = g.current_user_id


    #if not an instance of boolean return error
    if not isinstance(usd_to_lbp, bool):
        return _json_error("Direction must be boolean", 400)

    #validating currency types and returning error if invalid
    try:
        usd_amount = float(usd_amount) if usd_amount is not None else 0
        lbp_amount = float(lbp_amount) if lbp_amount is not None else 0

    except (ValueError, TypeError):
        return _json_error("Amounts must be numbers", 400)

    # user provides only the amount of the currency they are selling
    if usd_to_lbp:
        if usd_amount <= 0:
            return _json_error("usd_amount must be greater than 0 for USD to LBP", 400)
        if lbp_amount > 0:
            return _json_error("Do not provide lbp_amount for USD to LBP transactions", 400)
    else:
        if lbp_amount <= 0:
            return _json_error("lbp_amount must be greater than 0 for LBP to USD", 400)
        if usd_amount > 0:
            return _json_error("Do not provide usd_amount for LBP to USD transactions", 400)

    if usd_to_lbp:
        base_currency = "USD"
        quote_currency = "LBP"
    else:
        base_currency = "LBP"
        quote_currency = "USD"
    
    # get latest exchange rate for the pair if available and not flagged as anomalous
    latest_rate = RateService.get_latest_rate(base_currency, quote_currency)
    if not latest_rate:
        return _json_error("Exchange rate is temporarily unavailable. Please try again later.", 503)

    if latest_rate.is_flagged:
        return _json_error("Current exchange rate is temporarily unavailable due to detected anomalies. Please try again later.", 503)

    try:
        #lock the user's balance row for update
        user_balance = db.session.query(UserBalance).filter_by(user_id=user_id).with_for_update().first()
        if not user_balance:
            return _json_error("User balance not found", 400)

        # compute output amount and update user balance
        if usd_to_lbp:
            lbp_amount = usd_amount * latest_rate.rate_value
            if user_balance.usd_amount < usd_amount:
                return _json_error(
                    f"Insufficient USD balance. Required: {usd_amount}, Available: {user_balance.usd_amount}",
                    400,
                )
                #sufficient balance, update it
            user_balance.usd_amount -= usd_amount
            user_balance.lbp_amount += lbp_amount
        else:
            #rate is in LBP per 1 USD, so converting LBP to USD should divide by rate
            usd_amount = lbp_amount / latest_rate.rate_value
            if user_balance.lbp_amount < lbp_amount:
                return _json_error(
                    f"Insufficient LBP balance. Required: {lbp_amount}, Available: {user_balance.lbp_amount}",
                    400,
                )
            #sufficient balance, update it
            user_balance.lbp_amount -= lbp_amount
            user_balance.usd_amount += usd_amount

        user_balance.updated_at = datetime.now(timezone.utc)

        #input has been validated, create transaction instance
        t = Transaction(
            usd_amount=usd_amount,
            lbp_amount=lbp_amount,
            usd_to_lbp=usd_to_lbp,
            user_id=user_id,
        )
        db.session.add(t)
        #commit user and transaction changes to db
        db.session.commit()

        #create notification for user about the transaction    
        direction = 'USD to LBP' if usd_to_lbp else 'LBP to USD'
        msg = f"Transaction completed: {usd_amount} USD, {lbp_amount} LBP, Direction: {direction}."
        create_notification(user_id, msg, 'transaction')
        #and create an audit log entry for the transaction creation
        create_audit_log(
            action_type=AuditActionType.TRANSACTION_CREATED,
            description=f"Transaction created: USD {usd_amount}, LBP {lbp_amount}, Direction: {'USD to LBP' if usd_to_lbp else 'LBP to USD' }.",
            user_id=user_id,
            entity_type="Transaction",
            entity_id=t.id,
            ip_address=request.remote_addr
        )

        return jsonify(
            {
                "message": "Transaction created successfully",
                "applied_rate": latest_rate.rate_value,
                "transaction": transaction_schema.dump(t),
                "updated_balance": {
                    "usd_balance": user_balance.usd_amount,
                    "lbp_balance": user_balance.lbp_amount,
                },
                # Backward-compatible payload for older frontend code.
                "balance": {
                    "usd_amount": user_balance.usd_amount,
                    "lbp_amount": user_balance.lbp_amount,
                }
            }
        ), 201
    except HTTPException:
        raise
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Transaction could not be processed"}), 500

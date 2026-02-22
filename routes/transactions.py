from flask import Blueprint, request, jsonify, abort
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
@transactions_bp.route('/transactions', methods=['POST'])
@critical_rate_limit
@jwt_required
def add_transaction():
    data = request.json

    if not data:
        return abort(400, "Invalid JSON payload")
    
    usd_amount = data.get("usd_amount", 0)
    lbp_amount = data.get("lbp_amount", 0)
    usd_to_lbp = data.get("usd_to_lbp")

    user_id = jwtAuth.get_auth_user(request)


    #if not an instance of boolean return error
    if not isinstance(usd_to_lbp, bool):
        return abort(400, "Direction must be boolean")

    #validating currency types and returning error if invalid
    try:
        usd_amount = float(usd_amount) if usd_amount is not None else 0
        lbp_amount = float(lbp_amount) if lbp_amount is not None else 0

    except (ValueError, TypeError):
        return abort(400, "Amounts must be numbers")

    # user provides only the amount of the currency they are selling
    if usd_to_lbp:
        if usd_amount <= 0:
            return abort(400, "usd_amount must be greater than 0 for USD to LBP")
        if lbp_amount > 0:
            return abort(400, "Do not provide lbp_amount for USD to LBP transactions")
    else:
        if lbp_amount <= 0:
            return abort(400, "lbp_amount must be greater than 0 for LBP to USD")
        if usd_amount > 0:
            return abort(400, "Do not provide usd_amount for LBP to USD transactions")

    if usd_to_lbp:
        base_currency = "USD"
        quote_currency = "LBP"
    else:
        base_currency = "LBP"
        quote_currency = "USD"
    
    # get latest exchange rate for the pair if available and not flagged as anomalous
    latest_rate = RateService.get_latest_rate(base_currency, quote_currency)
    if not latest_rate:
        return abort(503, "Exchange rate is temporarily unavailable. Please try again later.")

    if latest_rate.is_flagged:
        return abort(503, "Current exchange rate is temporarily unavailable due to detected anomalies. Please try again later.")   

    try:
        #lock the user's balance row for update
        user_balance = db.session.query(UserBalance).filter_by(user_id=user_id).with_for_update().first()
        if not user_balance:
            return abort(400, "User balance not found")

        # compute output amount and update user balance
        if usd_to_lbp:
            lbp_amount = usd_amount * latest_rate.rate_value
            if user_balance.usd_amount < usd_amount:
                abort(400, f"Insufficient USD balance. Required: {usd_amount}, Available: {user_balance.usd_amount}")
                #sufficient balance, update it
            user_balance.usd_amount -= usd_amount
            user_balance.lbp_amount += lbp_amount
        else:
            #rate is in LBP per 1 USD, so converting LBP to USD should divide by rate
            usd_amount = lbp_amount / latest_rate.rate_value
            if user_balance.lbp_amount < lbp_amount:
                abort(400, f"Insufficient LBP balance. Required: {lbp_amount}, Available: {user_balance.lbp_amount}")
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
                "balance": {
                    "usd_amount": user_balance.usd_amount,
                    "lbp_amount": user_balance.lbp_amount
                }
            }
        ), 201
    except HTTPException:
        raise
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Transaction could not be processed"}), 500

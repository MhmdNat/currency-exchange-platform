from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, abort, g
from werkzeug.exceptions import HTTPException
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from model.offer import Offer, OfferSchema
from model.trade import Trade, TradeSchema
from model.user import User
from model.transaction import Transaction
from model.userBalance import UserBalance
from jwtAuth import jwt_required
from extensions import db

offers_bp = Blueprint('offers', __name__)
limiter = Limiter(key_func=get_remote_address)

offer_schema = OfferSchema()
trade_schema = TradeSchema(many=True)

#create offers endpoint
@offers_bp.route("/offers", methods=["POST"])
@limiter.limit("10 per minute")
@jwt_required
def create_offer():
    data = request.json
    if not data:
        abort(400, "INVALID JSON PAYLOAD")

    user_id=g.current_user_id

    # Required fields
    required_fields = ["from_currency", "to_currency", "amount", "exchange_rate"]

    for field in required_fields:
        if field not in data:
            abort(400, f"MISSING FIELD: {field}")

    from_currency = data.get("from_currency").upper()
    to_currency = data.get("to_currency").upper()
    amount = data.get("amount")
    exchange_rate = data.get("exchange_rate")

    # Validate currencies
    allowed_currencies = ["USD", "LBP"]

    if from_currency not in allowed_currencies:
        abort(400, "INVALID from_currency")

    if to_currency not in allowed_currencies:
        abort(400, "INVALID to_currency")

    if from_currency == to_currency:
        abort(400, "CANNOT EXCHANGE SAME CURRENCY")

    # Validate values
    try:
        amount = float(amount)
        exchange_rate = float(exchange_rate)
    except (ValueError, TypeError):
        abort(400, "AMOUNT AND EXCHANGE_RATE MUST BE NUMBERS")

    if amount <= 0:
        abort(400, "AMOUNT MUST BE GREATER THAN 0")

    if exchange_rate <= 0:
        abort(400, "EXCHANGE_RATE MUST BE GREATER THAN 0")

    # Subtract maker funds immediately
    try:
        maker_balance = db.session.query(UserBalance).filter_by(user_id=user_id).with_for_update().first()
        if not maker_balance:
            abort(400, "Maker balance not found")

        if from_currency == "USD":
            if maker_balance.usd_amount < amount:
                abort(400, "Insufficient USD balance to create offer")
            maker_balance.usd_amount -= amount
        else:
            if maker_balance.lbp_amount < amount:
                abort(400, "Insufficient LBP balance to create offer")
            maker_balance.lbp_amount -= amount

        # Create Offer
        offer = Offer(
            user_id=user_id,
            from_currency=from_currency,
            to_currency=to_currency,
            amount_total=amount,
            exchange_rate=exchange_rate,
        )

        db.session.add(offer)
        db.session.commit()

        return jsonify({
            "message": "Offer created successfully",
            "offer": offer_schema.dump(offer)
        }), 201
    except HTTPException:
        raise
    except Exception as e:
        db.session.rollback()
        print(f"error occured {str(e)}")
        abort(500, "Could not create offer")

    
@offers_bp.route("/offers", methods=["GET"])
@limiter.limit("10 per minute")
@jwt_required
def get_offers():

    user_id = g.current_user_id
    direction = request.args.get("direction")

    if not direction:
        abort(400, "MISSING direction PARAMETER")

    direction = direction.lower()

    if direction not in ["buy", "sell"]:
        abort(400, "direction MUST BE 'buy' OR 'sell'")

    query = Offer.query.filter(
        Offer.status.in_(["OPEN", "PARTIAL"]),
        Offer.amount_remaining > 0
    )

    # User wants to BUY USD, so we want USD sellers
    if direction == "buy":
        query = query.filter(
            Offer.from_currency == "USD",
            Offer.to_currency == "LBP"
        ).order_by(Offer.exchange_rate.asc())

    # User wants to SELL USD, so we want LBP sellers
    elif direction == "sell":
        query = query.filter(
            Offer.from_currency == "LBP",
            Offer.to_currency == "USD"
        ).order_by(Offer.exchange_rate.desc())

    offers = query.limit(20).all()

    schema = OfferSchema(many=True)
    return jsonify(schema.dump(offers)), 200


@offers_bp.route("/offers/<int:offer_id>/accept", methods=["POST"])
@jwt_required
def accept_offer(offer_id):
    user_id = g.current_user_id
    data = request.json

    #validate request body
    if not data or "amount" not in data:
        abort(400, "Missing 'amount' in request body")

    try:
        requested_amount = float(data["amount"])
    except (ValueError, TypeError):
        abort(400, "'amount' must be a number")

    if requested_amount <= 0:
        abort(400, "'amount' must be greater than 0")

    try:
        # Start transaction and lock the offer row with withforupdate
        # any other session trying to access the same row has to wait
        #this prevents overselling or race conditions
        offer = db.session.query(Offer).filter_by(id=offer_id).with_for_update().first()
        if not offer:
            abort(404, "Offer not found")

        if offer.user_id == user_id:
            abort(400, "Cannot accept your own offer")

        if offer.status not in ["OPEN", "PARTIAL"]:
            abort(400, f"Offer is not available (status={offer.status})")

        if requested_amount > offer.amount_remaining:
            abort(400, f"Requested amount exceeds remaining offer ({offer.amount_remaining})")

        # Get taker and maker balances with lock
        taker_balance = db.session.query(UserBalance).filter_by(user_id=user_id).with_for_update().first()
        if not taker_balance:
            abort(400, "Taker balance not found")

        maker_balance = db.session.query(UserBalance).filter_by(user_id=offer.user_id).with_for_update().first()
        if not maker_balance:
            abort(400, "Maker balance not found")

        # Calculate what the taker will give to maker
        amount_to = requested_amount * offer.exchange_rate

        # Determine transaction values based on offer direction
        if offer.from_currency == "USD": # so taker is buying usd
            usd_amount = requested_amount # maker gives USD
            lbp_amount = amount_to # taker gives LBP
            usd_to_lbp = False
            dir = "buy"
        else:
            usd_amount = amount_to # taker receives USD
            lbp_amount = requested_amount # maker gives LBP
            usd_to_lbp = True
            dir = "sell"

        # Check if taker has sufficient balance
        if usd_to_lbp:
            if taker_balance.usd_amount < usd_amount:
                abort(400, f"Insufficient USD balance. Required: {usd_amount}, Available: {taker_balance.usd_amount}")
        else:
            if taker_balance.lbp_amount < lbp_amount:
                abort(400, f"Insufficient LBP balance. Required: {lbp_amount}, Available: {taker_balance.lbp_amount}")

        # Get usernames for maker and taker
        maker_username = User.query.filter_by(id=offer.user_id).first()
        taker_username = User.query.filter_by(id=user_id).first()
        maker_username = maker_username.username if maker_username else "Unknown"
        taker_username = taker_username.username if taker_username else "Unknown"

        # Create Trade record
        trade = Trade(
            offer_id=offer.id,
            maker_id=offer.user_id,
            taker_id=user_id,
            maker_username=maker_username,
            taker_username=taker_username,
            amount_from=requested_amount, # amount that taker will get
            amount_to=amount_to,
            direction=dir, # specifies if taker was buying or selling usd
            executed_rate=offer.exchange_rate
        )
        db.session.add(trade)

        transaction = Transaction(
            usd_amount=usd_amount,
            lbp_amount=lbp_amount,
            usd_to_lbp=usd_to_lbp,
            user_id=user_id # logs the taker which is current user
        )
        db.session.add(transaction)

        # Update balances: maker's sell currency was subtracted at offer creation,
        #so here we only credit the maker with the amount to and update the taker balance.
        if offer.from_currency == "USD":
            # Maker sold USD at creation; on accept, maker receives LBP, taker gives LBP and receives USD
            taker_balance.lbp_amount -= lbp_amount
            taker_balance.usd_amount += usd_amount
            maker_balance.lbp_amount += lbp_amount
        else:
            # Maker sold LBP at creation; on accept, maker receives USD, taker gives USD and receives LBP
            taker_balance.usd_amount -= usd_amount
            taker_balance.lbp_amount += lbp_amount
            maker_balance.usd_amount += usd_amount

        maker_balance.updated_at = datetime.now(timezone.utc)
        taker_balance.updated_at = datetime.now(timezone.utc)
        # Update offer remaining amount
        offer.amount_remaining -= requested_amount
        if offer.amount_remaining == 0:
            offer.status = "FILLED"
        else:
            offer.status = "PARTIAL"

        db.session.commit()

        return jsonify({
            "message": "Offer accepted successfully",
            "trade_id": trade.id,
            "offer_status": offer.status,
            "amount_remaining": offer.amount_remaining
        }), 201

    except HTTPException:
        raise  # Re-raise HTTP exceptions (like abort(400)) to preserve status codes
    except Exception as e:
        db.session.rollback()
        print(f"error occured {str(e)}")
        abort(500, "Trade offer could not be accepted")


@offers_bp.route("/offers/<int:offer_id>/cancel", methods=["POST"])
@jwt_required
def cancel_offer(offer_id):
    user_id = g.current_user_id

    try:
        offer = db.session.query(Offer).filter_by(id=offer_id).with_for_update().first()
        if not offer:
            abort(404, "Offer not found")

        if offer.user_id != user_id:
            abort(403, "Only the offer owner can cancel the offer") #forbidden acttion

        if offer.status not in ["OPEN", "PARTIAL"]:
            abort(400, f"Offer cannot be cancelled (status={offer.status})")

        # Refund remaining amount_remaining to maker in the offer.from_currency
        refund_amount = offer.amount_remaining
        if refund_amount > 0:
            maker_balance = db.session.query(UserBalance).filter_by(user_id=offer.user_id).with_for_update().first()
            if not maker_balance:
                abort(400, "Maker balance not found for refund")
            if offer.from_currency == "USD":
                maker_balance.usd_amount += refund_amount
            else:
                maker_balance.lbp_amount += refund_amount

        # mark as cancelled and zero remaining amount
        offer.status = "CANCELLED"
        offer.amount_remaining = 0
        db.session.commit()

        return jsonify({"message": "Offer cancelled successfully", "offer_id": offer.id}), 200

    except HTTPException:
        raise
    except Exception as e:
        db.session.rollback()
        print(f"error occured {str(e)}")
        abort(500, "Offer could not be cancelled")


@offers_bp.route("/trades", methods=["GET"])
@jwt_required
def get_my_trades():
    user_id = g.current_user_id

    try:
        # include trades where user was maker or taker
        trades = db.session.query(Trade).filter(
            (Trade.maker_id == user_id) | (Trade.taker_id == user_id)
        ).order_by(Trade.created_at.desc()).limit(100).all()

        return jsonify({"trades": trade_schema.dump(trades)}), 200

    except Exception as e:
        print(f"error occured {str(e)}")
        abort(500, "Could not retrieve trades")
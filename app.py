from flask import Flask, request, abort, jsonify, g
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from model.transaction import Transaction, TransactionSchema, db, ma
from model.user import User, UserSchema
from extensions import bcrypt
import jwtAuth
from jwtAuth import jwt_required
from datetime import datetime, timedelta, timezone
from jwt import ExpiredSignatureError, InvalidTokenError
from db_config import db_config
from flask_cors import CORS
import utils
from model.offer import Offer, OfferSchema
from model.trade import Trade
from model.userBalance import UserBalance

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = db_config
CORS(app)


db.init_app(app)
ma.init_app(app)
bcrypt.init_app(app)

limiter = Limiter(app=app, key_func=get_remote_address)
transaction_schema=TransactionSchema()
transactions_schema=TransactionSchema(many=True)
user_schema=UserSchema()
offer_schema=OfferSchema()


#get exchange rate with rate limiting
@app.route('/exchangeRate', methods=['GET'])
@limiter.limit("10 per minute")

def get_exchange_rate():
    threeDays = timedelta(days=3)
    currentTime = datetime.now(timezone.utc)
    threeDaysAgo = currentTime - threeDays

    #get transactions by time
    usd_to_lbp_transactions, lbp_to_usd_transactions = utils.get_transactions_by_date(
        threeDaysAgo, 
        currentTime
    )

    # get rates of transactions
    usd_to_lbp_rates_weighted, lbp_to_usd_rates_weighted = utils.get_transaction_rates_weighted(
        usd_to_lbp_transactions,
        lbp_to_usd_transactions
    )

    # final rate of each direction
    avg_weighted_usd_to_lbp_rate = utils.get_weighted_avg_rate(usd_to_lbp_rates_weighted)
    avg_weighted_lbp_to_usd_rate = utils.get_weighted_avg_rate(lbp_to_usd_rates_weighted)

    return jsonify({
        "message":"Retrieved average exchange rates",
        "usd_to_lbp":avg_weighted_usd_to_lbp_rate,
        "lbp_to_usd":avg_weighted_lbp_to_usd_rate
    }), 200


# get exchange rate with analytics
@app.route("/exchangeRate/analytics", methods=["GET"])
@limiter.limit("10 per minute")

def get_exchange_rate_analytics():
    start_str = request.args.get("start") #this would be "2026-02-16"
    end_str = request.args.get("end")

    #converts to datetime objects, defaults to three days ago and current time
    try:
        start_time, end_time = utils.convert_str_to_time(start_str, end_str)
    except ValueError:
        return jsonify({
        "error": "Invalid date format. Use YYYY-MM-DD"
        }), 400
    
    # get transactions
    usd_to_lbp_transactions, lbp_to_usd_transactions = utils.get_transactions_by_date(
        start_time, end_time
    )

    #get weighted rates
    usd_to_lbp_rates_weighted, lbp_to_usd_rates_weighted = utils.get_transaction_rates_weighted(
        usd_to_lbp_transactions, lbp_to_usd_transactions
    )

    # compute stats for USD to LBP
    usd_rates = [r for r, w in usd_to_lbp_rates_weighted]  # plain rates
    usd_stats = {
        "min": min(usd_rates) if usd_rates else None,
        "max": max(usd_rates) if usd_rates else None,
        "weighted_avg": utils.get_weighted_avg_rate(usd_to_lbp_rates_weighted),
        #pct change from first rate to last rate
        "pct_change": ((usd_rates[-1] - usd_rates[0]) / usd_rates[0] * 100) if len(usd_rates) > 1 else 0
    }

    # compute stats for LBP to USD
    lbp_rates = [r for r, w in lbp_to_usd_rates_weighted] #plain rates
    lbp_stats = {
        "min": min(lbp_rates) if lbp_rates else None,
        "max": max(lbp_rates) if lbp_rates else None,
        "weighted_avg": utils.get_weighted_avg_rate(lbp_to_usd_rates_weighted),
        "pct_change": ((lbp_rates[-1] - lbp_rates[0]) / lbp_rates[0] * 100) if len(lbp_rates) > 1 else 0
    }

    return jsonify({
        "message": "Exchange rate analytics retrieved",
        "usd_to_lbp": usd_stats,
        "lbp_to_usd": lbp_stats
    }), 200


# FEATURE 2
#Exchange Rate History Graph Support (Time-Series Data)

@app.route("/exchangeRate/history", methods=["GET"])
@limiter.limit("10 per minute")
#get transactions created by authenticated user
def get_exchange_rate_history():

    #returns lists of rates per interval
    start_str = request.args.get("start")
    end_str = request.args.get("end")
    interval = request.args.get("interval", "daily") #default is daily

    #converts to datetime objects, defaults to three days ago and current time
    try:
        start_time, end_time = utils.convert_str_to_time(start_str, end_str)
    except ValueError:
        return jsonify({
        "error": "Invalid date format. Use YYYY-MM-DD"
        }), 400
    
    usd_txns, lbp_txns = utils.get_transactions_by_date(start_time, end_time)

    # group transactions by interval
    if interval == "hourly":
        func = lambda t: t.added_date.replace(minute=0, second=0, microsecond=0) # keep day but round hour down
        
    else:  # daily
        func = lambda t: t.added_date.date()

    usd_timestamps, usd_rates = utils.extract_timestamps_and_rates(usd_txns, func)
    lbp_timestamps, lbp_rates = utils.extract_timestamps_and_rates(lbp_txns, func)

    return jsonify({
        "usd_to_lbp": {
            "timestamps": usd_timestamps, 
            "rates": usd_rates
            },
        "lbp_to_usd": {
            "timestamps": lbp_timestamps, 
            "rates": lbp_rates
            },
    }), 200



@app.route("/transaction", methods=["GET"])
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
@app.route('/transaction', methods=['POST'])
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
    # add to the session and commit the change to save to db
    db.session.add(t)
    db.session.commit()
    return jsonify(
        {
            "message":"Transaction created successfully",
            "transaction": transaction_schema.dump(t),

        }
    ), 201


@app.route('/user', methods=["POST"])
@limiter.limit("10 per minute")

def add_user():
    data = request.json
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400
    user_name = data.get("user_name")
    password = data.get("password")

    # validate if user_name and password are strings
    if not (
        isinstance(user_name, str) and 
        isinstance(password, str)
        ): 
        return jsonify({"error":"Username and Password have to be strings"}), 400

    # verify that they are not empty
    if not user_name or not password :
        return jsonify({"error":"Username and Password can not be empty"}), 400

    #check if username exists in db as db check not enough
    existing = db.session.execute(
        db.select(User).where(User.user_name==user_name)
    ).scalar_one_or_none()

    if existing:
        return jsonify({"error":f'Username ({user_name}) already exists'}), 409

    #create user instance,
    u = User(
        user_name,
        password
    )

    #add to session and commit the change
    db.session.add(u)

    # Create initial balance for the user
    balance = UserBalance(user_id=u.id, usd_amount=0.0, lbp_amount=0.0)
    db.session.add(balance)

    db.session.commit()
    
    #return json containing 
    return jsonify(
        {
            "message":"User created successfully",
            "user": user_schema.dump(u),
        }
    ) , 201


@app.route("/authentication", methods=["POST"])
@limiter.limit("10 per minute")
def authenticate():
    data = request.json
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400
    
    user_name = data.get("user_name")
    password = data.get("password")

    # validate if user_name and password are strings
    if not (
        isinstance(user_name, str) and 
        isinstance(password, str)
        ): 
        return jsonify({"error":"Username and Password have to be strings"}), 400

    # verify that they are not empty
    if not user_name or not password :
        return jsonify({"error":"Username and Password can not be empty"}), 400

    user = db.session.execute(
        db.select(User).where(User.user_name==user_name)
    ).scalar_one_or_none()

    #unauthorized is 401, 403 is forbidden
    if not user:
        return jsonify({"error":f'Username ({user_name}) does not exist'}), 401
    
    #users exists need to check password
    correct_password=bcrypt.check_password_hash(user.hashed_password, password)
    if not correct_password:
        return jsonify({"error":'Password does not match'}), 401

    #correct initials at this stage create token
    token=jwtAuth.create_token(user.id)
    return jsonify({
        "token":token
    }), 200


###########################
#OFFERS AND TRADES SECTION

#create offers endpoint

@app.route("/offers", methods=["POST"])
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


    #need to check if user has sufficient balance to create the offer
    # Lock user balance row for maker
    maker_balance = db.session.query(UserBalance)\
        .filter_by(user_id=user_id)\
        .with_for_update().first()

    if not maker_balance:
        abort(400, "User balance not found")

    # Determine which currency balance to check
    if from_currency == "USD":
        if maker_balance.usd_amount < amount:
            abort(400, "Insufficient USD balance to post offer")
        maker_balance.usd_amount -= amount
    else:
        if maker_balance.lbp_amount < amount:
            abort(400, "Insufficient LBP balance to post offer")
        maker_balance.lbp_amount -= amount
        
    # Update maker's balance in the database
    db.session.add(maker_balance)
    db.session.flush()  # Ensure changes are flushed to DB before proceeding

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

    
@app.route("/offers", methods=["GET"])
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



@app.route("/offers/<int:offer_id>/accept", methods=["POST"])
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
            if taker_balance.usd_amount < amount_to:
                abort(400, f"Insufficient USD balance. Required: {amount_to}, Available: {taker_balance.usd_amount}")
        else:
            if taker_balance.lbp_amount < amount_to:
                abort(400, f"Insufficient LBP balance. Required: {amount_to}, Available: {taker_balance.lbp_amount}")

        # Create Trade record
        trade = Trade(
            offer_id=offer.id,
            maker_id=offer.user_id,
            taker_id=user_id,
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

        # Update balances
        if usd_to_lbp:
            taker_balance.usd_amount -= usd_amount
            taker_balance.lbp_amount += lbp_amount
            maker_balance.usd_amount += usd_amount
            maker_balance.lbp_amount -= lbp_amount
        else:
            taker_balance.usd_amount += usd_amount
            taker_balance.lbp_amount -= lbp_amount
            maker_balance.usd_amount -= usd_amount
            maker_balance.lbp_amount += lbp_amount

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

    except Exception as e:
        db.session.rollback()
        print(f"error occured {str(e)}")
        abort(500, "Trade offer could not be accepted")




if __name__ == "__main__":
    app.run(debug=False)
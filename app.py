from flask import Flask, request, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from model.transaction import Transaction, TransactionSchema, db, ma
from model.user import User, UserSchema
from extentions import bcrypt
import jwtAuth
from datetime import datetime, timedelta, timezone
from jwt import ExpiredSignatureError, InvalidTokenError
from db_config import db_config
from flask_cors import CORS
import utils

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

    #default if parameters not provided correctly
    current_time = datetime.now(timezone.utc)
    three_days_ago = current_time - timedelta(days=3)

    try:
        start_time = datetime.fromisoformat(start_str) if start_str else three_days_ago
        end_time = datetime.fromisoformat(end_str) if end_str else current_time
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


#get transactions created by authenticated user
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
        print("error:", e)
    except  ExpiredSignatureError as e:
        user_id = None
        print("error: ", e)


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


if __name__ == "__main__":
    app.run(debug=False)
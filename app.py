from flask import Flask, request, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from transaction import Transaction, TransactionSchema, db, ma
from user import User, UserSchema
from extentions import bcrypt
import jwt
import jwtAuth



# Load environment variables from the .env file
load_dotenv()
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
SECRET_KEY = os.getenv("SECRET_KEY")


app = Flask(__name__)
app.config[
    'SQLALCHEMY_DATABASE_URI'
    ] = f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@127.0.0.1:3306/exchange'


db.init_app(app)
ma.init_app(app)
bcrypt.init_app(app)

limiter = Limiter(app=app, key_func=get_remote_address)
transaction_schema=TransactionSchema()
user_schema=UserSchema()


#get exchange rate with rate limiting
@app.route('/exchangeRate', methods=['GET'])
@limiter.limit("10 per minute")

def get_exchange_rate():

    # transactions retrieved as lists
    usd_to_lbp_transactions = db.session.execute(
        db.select(Transaction).where(Transaction.usd_to_lbp == True)
    ).scalars().all()
    lbp_to_usd_transactions = db.session.execute(
        db.select(Transaction).where(Transaction.usd_to_lbp == False)
    ).scalars().all()


    # list of each transactions rates
    usd_to_lbp_rates = [
        (t.lbp_amount / t.usd_amount) for t in usd_to_lbp_transactions
    ]
    lbp_to_usd_rates = [
        (t.usd_amount / t.lbp_amount) for t in lbp_to_usd_transactions
    ]

    # final rate of each direction
    avg_usd_to_lbp_rate =  (
        sum(usd_to_lbp_rates) / len(usd_to_lbp_rates)
        if len(usd_to_lbp_rates)>0
        else None
    )
        
    avg_lbp_to_usd_rate = (
        sum(lbp_to_usd_rates) / len(lbp_to_usd_rates) 
        if len(lbp_to_usd_rates) > 0 
        else None
    )

    return jsonify({
        "message":"Retrieved average exchange rates",
        "usd_to_lbp":avg_usd_to_lbp_rate,
        "lbp_to_usd":avg_lbp_to_usd_rate
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
        usd_to_lbp=usd_to_lbp
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
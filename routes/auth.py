from flask import Blueprint, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from model.user import User, UserSchema
from model.userBalance import UserBalance
from extensions import bcrypt, db
import jwtAuth

auth_bp = Blueprint('auth', __name__)
limiter = Limiter(key_func=get_remote_address)

user_schema = UserSchema()

@auth_bp.route('/user', methods=["POST"])
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
    db.session.flush()  # Flush to assign user.id

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


@auth_bp.route("/authentication", methods=["POST"])
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
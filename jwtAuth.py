import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from datetime import datetime, timezone, timedelta
import os
from functools import wraps
from flask import request, abort, g
from model.user import User

SECRET_KEY=os.getenv("SECRET_KEY")

def create_token(user_id):
    payload = {
    'exp': datetime.now(timezone.utc) + timedelta(days=4),
    'iat': datetime.now(timezone.utc),
    'sub': str(user_id) #sub must be string
    }
    
    token = jwt.encode (
        payload, 
        SECRET_KEY,
        algorithm='HS256'
    )
    return token


def extract_auth_token(auth_header):
    if not auth_header:
        return None
    parts = auth_header.split()

    if len(parts) !=2 or parts[0] != "Bearer":
          return None
     
    token = parts[1]
    return token

        
def decode_token(token):
    payload = jwt.decode(
        token, 
        SECRET_KEY, 
        algorithms=['HS256']
        )
    return int(payload.get('sub')) # convert string sub to int

def get_auth_user(authenticated_request):
    auth_header = authenticated_request.headers.get('Authorization')
    print(auth_header)
    token = extract_auth_token(auth_header)
    
    return decode_token(token) if token else None




def jwt_required(f):
    #wraps the route function to enforce JWT authentication
    @wraps(f)
    #this decorator will be applied to routes that require authentication
    #the arguments and return value of the original function will be preserved  
    #*args means positional arguments, **kwargs means keyword arguments, both are passed to the original function
    def decorated(*args, **kwargs):
        try:
            user_id = get_auth_user(request)
        except InvalidTokenError:
            abort(401, "Invalid token")
        except ExpiredSignatureError:
            abort(401, "Expired token")

        if not user_id:
            abort(401, "Unauthorized user")

        g.current_user_id = user_id
        return f(*args, **kwargs)
    return decorated

@jwt_required
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = g.current_user_id
        user = User.query.get(user_id)
        if not user or user.role != "ADMIN" or user.status != "ACTIVE":
            abort(403, "Admin privileges required")
        return f(*args, **kwargs)
    return decorated
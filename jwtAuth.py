import jwt
import datetime
import os

SECRET_KEY=os.getenv("SECRET_KEY")

def create_token(user_id):
    payload = {
    'exp': datetime.datetime.utcnow() + datetime.timedelta(days=4),
    'iat': datetime.datetime.utcnow(),
    'sub': user_id
    }
    return jwt.encode (
        payload, SECRET_KEY,
        algorithm='HS256'
    )
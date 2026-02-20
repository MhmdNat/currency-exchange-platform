from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from extensions import bcrypt, db, ma
from db_config import db_config
from flask_cors import CORS

# Import blueprints
from routes.auth import auth_bp
from routes.exchange import exchange_bp
from routes.transactions import transactions_bp
from routes.offers import offers_bp

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = db_config
CORS(app)

db.init_app(app)
ma.init_app(app)
bcrypt.init_app(app)

limiter = Limiter(app=app, key_func=get_remote_address)

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(exchange_bp)
app.register_blueprint(transactions_bp)
app.register_blueprint(offers_bp)

if __name__ == "__main__":
    app.run(debug=False)

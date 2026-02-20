from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from flask_bcrypt import Bcrypt

ma = Marshmallow()
db = SQLAlchemy()
bcrypt = Bcrypt()
from sqlalchemy.orm import Mapped, mapped_column
from extensions import db, ma, bcrypt
from .userPreferences import UserPreferences

class User(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    user_name: Mapped[str] = mapped_column(db.String(30), unique=True)
    hashed_password: Mapped[str] = mapped_column(db.String(128))
    
    preferences = db.relationship('UserPreferences', uselist=False)
    #one directional relationship to UserPreferences, uselist=False indicates one-to-one relationship

    def __init__(self, user_name, password):
        super().__init__()
        self.user_name = user_name
        self.hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

class  UserSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model=User
        fields=('id', 'user_name')
from extensions import db
from datetime import datetime, timezone

class UserBalance(db.Model):
    __tablename__ = "user_balance"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
    usd_amount = db.Column(db.Float, nullable=False, default=0.0)
    lbp_amount = db.Column(db.Float, nullable=False, default=0.0)
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    def __init__(self, user_id, usd_amount=0.0, lbp_amount=0.0):
        self.user_id = user_id
        self.usd_amount = usd_amount
        self.lbp_amount = lbp_amount
        self.updated_at = datetime.now(timezone.utc)

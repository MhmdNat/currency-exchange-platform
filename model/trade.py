from extentions import db
from datetime import datetime

class Trade(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    offer_id = db.Column(db.Integer, db.ForeignKey("offer.id"), nullable=False)

    #maker creates the offer
    #taker accepts
    maker_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    taker_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    amount_from = db.Column(db.Float, nullable=False)
    amount_to = db.Column(db.Float, nullable=False)

    executed_rate = db.Column(db.Float, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

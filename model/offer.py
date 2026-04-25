from extensions import db, ma
from datetime import datetime, timezone
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from marshmallow import fields
from marshmallow.fields import Method

class Offer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    creator = db.relationship("User", foreign_keys=[user_id], lazy="joined")

    from_currency = db.Column(db.String(3), nullable=False)
    to_currency = db.Column(db.String(3), nullable=False)

    amount_total = db.Column(db.Float, nullable=False)
    amount_remaining = db.Column(db.Float, nullable=False)

    exchange_rate = db.Column(db.Float, nullable=False)

    status = db.Column(db.String(20), default="OPEN")  # OPEN, PARTIAL, FILLED, CANCELLED
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    def __init__(
        self, 
        user_id, 
        from_currency, 
        to_currency, 
        amount_total, 
        exchange_rate,
    ):
        super(Offer, self).__init__(
            user_id=user_id,
            from_currency=from_currency,
            to_currency=to_currency,
            amount_total=amount_total,
            amount_remaining=amount_total, #init amount remaining to total
            exchange_rate=exchange_rate,
            status="OPEN", #make it open and add timestamp
            created_at=datetime.now(timezone.utc)
        )


class OfferSchema(ma.SQLAlchemyAutoSchema):
    creator_username = Method("get_creator_username")

    def get_creator_username(self, obj):
        if obj.creator:
            return obj.creator.user_name
        return None

    class Meta:
        model = Offer
        #tell marshmallow to include foreign key
        include_fk=True
        fields = (
            "id",
            "user_id",
            "creator_username",
            "from_currency",
            "to_currency",
            "amount_total",
            "amount_remaining",
            "exchange_rate",
            "status",
            "created_at",
        )

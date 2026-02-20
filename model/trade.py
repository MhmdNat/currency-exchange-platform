from extensions import db, ma
from datetime import datetime, timezone
from marshmallow import fields

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

    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    direction = db.Column(db.String(10), nullable=False)
    # values could be:
    # buy: taker is buying USD
    # sell: taker is selling USD


    def __init__(
        self,
        offer_id,
        maker_id,
        taker_id,
        amount_from,
        amount_to,
        executed_rate,
        direction
    ):
        super(Trade, self).__init__(
            offer_id=offer_id,
            maker_id=maker_id,
            taker_id=taker_id,
            amount_from=amount_from,
            amount_to=amount_to,
            executed_rate=executed_rate,
            direction=direction,
            created_at=datetime.now(timezone.utc)
        )


class TradeSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Trade
        include_fk = True
        fields = (
            "id",
            "offer_id",
            "maker_id",
            "taker_id",
            "amount_from",
            "amount_to",
            "executed_rate",
            "direction",
            "created_at"
        )

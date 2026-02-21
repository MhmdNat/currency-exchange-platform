from extensions import db, ma
from datetime import datetime, timezone

class RateAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    direction = db.Column(db.String(20), nullable=False)  # e.g., "BUY_USD", "SELL_USD"
    threshold_rate = db.Column(db.Float, nullable=False)
    condition = db.Column(db.String(10), nullable=False)  # "above" or "below"
    is_triggered = db.Column(db.Boolean, default=False)
    triggered_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    def __init__(self, user_id, direction, threshold_rate, condition):
        super(RateAlert, self).__init__(
            user_id=user_id,
            direction=direction,
            threshold_rate=threshold_rate,
            condition=condition,
            created_at=datetime.now(timezone.utc)
        )

class RateAlertSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = RateAlert
        include_fk = True
        fields = ("id", "user_id", "direction", "threshold_rate", "condition", "is_triggered", "triggered_at", "created_at")
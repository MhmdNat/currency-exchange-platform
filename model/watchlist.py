from extensions import db, ma
from datetime import datetime, timezone

class WatchlistItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    rate_alert_id = db.Column(db.Integer, db.ForeignKey("rate_alert.id"), nullable=True)

    item_type = db.Column(db.String(32), nullable=False)  # e.g., 'rate_threshold' or 'direction'
    direction = db.Column(db.String(10), nullable=True)   # BUY_USD or SELL_USD
    threshold_rate = db.Column(db.Float, nullable=True)
    label = db.Column(db.String(128), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    def __init__(self, user_id, item_type, direction=None, threshold_rate=None, label=None, rate_alert_id=None):
        super(WatchlistItem, self).__init__(
            user_id=user_id,
            item_type=item_type,
            direction=direction,
            threshold_rate=threshold_rate,
            label=label,
            rate_alert_id=rate_alert_id,
            created_at=datetime.now(timezone.utc)
        )

class WatchlistItemSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = WatchlistItem
        include_fk = True
        fields = ("id", "user_id", "rate_alert_id", "item_type", "direction", "threshold_rate", "label", "created_at")

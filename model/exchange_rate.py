from datetime import datetime, timezone
from extensions import db, ma

class ExchangeRate(db.Model):
    __tablename__ = 'exchange_rates'

    id = db.Column(db.Integer, primary_key=True)
    base_currency = db.Column(db.String(10), nullable=False)
    quote_currency = db.Column(db.String(10), nullable=False)
    rate_value = db.Column(db.Float, nullable=False)
    source = db.Column(db.String(32), nullable=False)  # 'external_api', 'internal_computed', 'manual_override'
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), nullable=False)
    is_flagged = db.Column(db.Boolean, default=False, nullable=False)
    anomaly_reason = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f'<ExchangeRate {self.base_currency}/{self.quote_currency} {self.rate_value}>'


class ExchangeRateSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = ExchangeRate
        fields = (
            "id",
            "base_currency",
            "quote_currency",
            "rate_value",
            "source",
            "created_at",
            "is_flagged",
            "anomaly_reason",
        )

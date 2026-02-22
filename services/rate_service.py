from datetime import datetime, timezone
from flask import abort 
from extensions import db  
from model.exchange_rate import ExchangeRate 


class RateService:
    # Threshold to consider a rate as an outlier: 10% change from last rate
    OUTLIER_THRESHOLD = 0.10
    # Allowed sources for rates
    VALID_SOURCES = {"external_api", "internal_computed", "manual_override"}
    # Allowed currency pairs in this platform (buy/sell USD only)
    ALLOWED_PAIRS = {("USD", "LBP"), ("LBP", "USD")}

    @staticmethod
    def validate_rate(new_rate):
        """Ensure the rate is numeric and greater than zero"""
        try:
            value = float(new_rate)
        except (TypeError, ValueError):
            abort(400, "Invalid rate_value. Must be a numeric value.")  # stop if not numeric

        if value <= 0:
            abort(400, "Invalid rate_value. Must be greater than zero.")  # stop if <=0
        return value

    @staticmethod
    def detect_outlier(new_rate, last_rate=None):
        """
        Compare new rate with last rate and detect if the change exceeds threshold
        Returns (is_outlier: bool, reason: str)
        """
        if last_rate is None or last_rate <= 0:
            return False, None  # cannot compare, so not an outlier

        # percentage change between new and last
        pct_change = abs(new_rate - last_rate) / last_rate

        if pct_change > RateService.OUTLIER_THRESHOLD:
            reason = (
                f"Rate shift {pct_change * 100:.2f}% exceeds "
                f"{RateService.OUTLIER_THRESHOLD * 100:.0f}% threshold"
            )
            return True, reason  # flagged as outlier with reason

        return False, None  # not an outlier

    @staticmethod
    def get_latest_rate(base_currency, quote_currency):
        """
        Fetch the most recent rate for a currency pair from the database
        Orders by creation time (newest first) and ID (tie-breaker)
        """
        # normalize inputs to upper-case codes
        base = base_currency.upper().strip() if base_currency else ''
        quote = quote_currency.upper().strip() if quote_currency else ''

        # enforce app scope: only USD/LBP and LBP/USD supported
        if (base, quote) not in RateService.ALLOWED_PAIRS:
            abort(400, "Only USD/LBP and LBP/USD rates are supported.")

        return (
            ExchangeRate.query.filter_by(
                base_currency=base,
                quote_currency=quote,
            )
            .order_by(ExchangeRate.created_at.desc(), ExchangeRate.id.desc()) # id is tie-breaker for same timestamp
            .first()  # only return the latest entry
        )

    @staticmethod
    def save_rate_if_valid(base_currency, quote_currency, rate_value, source):
        """
        Validates the rate and source, flags anomalies, and saves a new ExchangeRate entry
        """
        # normalize inputs: uppercase currency codes, strip whitespace
        normalized_base = (base_currency if base_currency else '').upper().strip()
        normalized_quote = (quote_currency if quote_currency else '').upper().strip()
        normalized_source = (source if source else '').strip()

        if not normalized_base or not normalized_quote:
            abort(400, "base_currency and quote_currency are required.")  # missing input

        #only USD/LBP and LBP/USD supported
        if (normalized_base, normalized_quote) not in RateService.ALLOWED_PAIRS:
            abort(400, "Only USD/LBP and LBP/USD rates are supported.")

        if normalized_source not in RateService.VALID_SOURCES:
            abort(
                400,
                "Invalid source. Allowed values: external_api, internal_computed, manual_override.",
            )

        # ensure rate is valid
        value = RateService.validate_rate(rate_value)

        # get latest rate for comparison
        latest_rate = RateService.get_latest_rate(normalized_base, normalized_quote)
        previous_value = latest_rate.rate_value if latest_rate else None

        # check if new rate should be flagged as an outlier
        is_flagged, anomaly_reason = RateService.detect_outlier(value, previous_value)

        # create new ExchangeRate entry
        rate = ExchangeRate(
            base_currency=normalized_base,
            quote_currency=normalized_quote,
            rate_value=value,
            source=normalized_source,
            created_at=datetime.now(timezone.utc),  # UTC timestamp
            is_flagged=is_flagged,
            anomaly_reason=anomaly_reason,
        )

        # save to database
        db.session.add(rate)
        db.session.commit()
        return rate

    @staticmethod
    def get_latest_rates_by_pair():
        """
        Returns latest rates for the two supported pairs only
        (USD/LBP and LBP/USD)
        """
        latest_rates = []

        # get latest SELL_USD direction rate (USD -> LBP)
        usd_to_lbp = RateService.get_latest_rate("USD", "LBP")
        if usd_to_lbp:
            latest_rates.append({"direction": "usd_to_lbp", "rate": usd_to_lbp})

        # get latest BUY_USD direction rate (LBP -> USD)
        lbp_to_usd = RateService.get_latest_rate("LBP", "USD")
        if lbp_to_usd:
            latest_rates.append({"direction": "lbp_to_usd", "rate": lbp_to_usd})

        return latest_rates

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from extensions import bcrypt, db, ma, limiter
from db_config import db_config
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timezone
import utils  
from model.notifications import Notification
from flask import jsonify

# Import blueprints
from routes.auth import auth_bp
from routes.exchange import exchange_bp
from routes.transactions import transactions_bp
from routes.offers import offers_bp
from routes.rateAlerts import rateAlerts_bp
from routes.watchlist import watchlist_bp
from routes.csvExports import csvExports_bp
from routes.preferences import preferences_bp
from routes.admin.endpoints import admin_bp
from routes.logs import logs_bp
from routes.notifications import notifications_bp
from routes.admin.analytics import analytics_bp
from routes.admin.rate_quality import rate_quality_bp

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = db_config
CORS(app)

db.init_app(app)
ma.init_app(app)
bcrypt.init_app(app)
limiter.init_app(app)

@app.errorhandler(429)
def rate_limit_exceeded(e):
    return jsonify({"error": "Too many requests. Please try again later."}), 429

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(exchange_bp)
app.register_blueprint(transactions_bp)
app.register_blueprint(offers_bp)
app.register_blueprint(rateAlerts_bp)
app.register_blueprint(watchlist_bp)
app.register_blueprint(csvExports_bp)
app.register_blueprint(preferences_bp)
app.register_blueprint(admin_bp) 
app.register_blueprint(logs_bp)
app.register_blueprint(notifications_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(rate_quality_bp)

# Alert checking function
def check_alerts():
    with app.app_context(): #This ensures the scheduler can access the database session and models properly
        #within the app
        from model.rateAlerts import RateAlert 
        from services.rate_service import RateService

        # Fetch latest stored rates for both supported pairs from the quality service
        latest_rates = RateService.get_latest_rates_by_pair()
        # Build an easy lookup map keyed by tuple: (base_currency, quote_currency)
        rates_by_pair = {}
        for item in latest_rates:
            rate_obj = item["rate"]
            pair_key = (rate_obj.base_currency, rate_obj.quote_currency)
            rates_by_pair[pair_key] = rate_obj.rate_value

        # Print latest rates every scheduler run for quick terminal monitoring
        usd_to_lbp_rate = rates_by_pair.get(("USD", "LBP"))
        lbp_to_usd_rate = rates_by_pair.get(("LBP", "USD"))
        print(
            f"[Rate Monitor] USD->LBP: {usd_to_lbp_rate} | "
            f"LBP->USD: {lbp_to_usd_rate}"
        )
        
        # Process only alerts that have not been triggered yet
        alerts = RateAlert.query.filter_by(is_triggered=False).all()
        for alert in alerts:
            # Map business direction to the underlying pair used for comparison
            if alert.direction == 'BUY_USD':
                # BUY_USD checks the configured LBP -> USD pair
                current_rate = rates_by_pair.get(("LBP", "USD"))
            else:
                # SELL_USD checks the configured USD -> LBP pair
                current_rate = rates_by_pair.get(("USD", "LBP"))

            # Skip this alert if we don't have a current rate for its pair
            if current_rate is None:
                continue  # No rate available

            # Trigger alert when threshold condition is met
            if (alert.condition == 'above' and current_rate > alert.threshold_rate) or \
               (alert.condition == 'below' and current_rate < alert.threshold_rate):
                alert.is_triggered = True
                alert.triggered_at = datetime.now(timezone.utc)
                # Store notification in db
                message = f"Alert triggered: {alert.direction} rate {current_rate} {alert.condition} {alert.threshold_rate}"
                utils.create_notification(alert.user_id, message, 'alert')
        # Persist all triggered alert updates in one commit
        db.session.commit()

# Set up scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(check_alerts, IntervalTrigger(seconds=60))  # Check every minute
scheduler.start()

if __name__ == "__main__":
    app.run(debug=False)

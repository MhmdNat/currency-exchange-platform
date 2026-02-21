from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from extensions import bcrypt, db, ma
from db_config import db_config
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timezone
import utils  

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

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = db_config
CORS(app)

db.init_app(app)
ma.init_app(app)
bcrypt.init_app(app)

limiter = Limiter(app=app, key_func=get_remote_address)

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

# Alert checking function
def check_alerts():
    with app.app_context(): #This ensures the scheduler can access the database session and models properly
        #within the app
        from model.rateAlerts import RateAlert 
        rates = utils.get_current_exchange_rates()
        
        alerts = RateAlert.query.filter_by(is_triggered=False).all()
        for alert in alerts:
            current_rate = rates.get('lbp_to_usd' if alert.direction == 'BUY_USD' else 'usd_to_lbp', 0)
            if current_rate is None:
                continue  # No rate available
            if (alert.condition == 'above' and current_rate > alert.threshold_rate) or \
               (alert.condition == 'below' and current_rate < alert.threshold_rate):
                alert.is_triggered = True
                alert.triggered_at = datetime.now(timezone.utc)
                print(f"Alert triggered for user {alert.user_id}: {alert.direction} rate {current_rate} {alert.condition} {alert.threshold_rate}")
        
        db.session.commit()

# Set up scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(check_alerts, IntervalTrigger(seconds=60))  # Check every minute
scheduler.start()

if __name__ == "__main__":
    app.run(debug=False)

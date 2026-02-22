from datetime import datetime
from extensions import db

class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    message = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    read = db.Column(db.Boolean, default=False)
    type = db.Column(db.String(50), nullable=False)  # e.g., 'alert', 'offer', 'trade'

    def __repr__(self):
        return f'<Notification {self.id}>'

from extensions import db
from sqlalchemy import Enum, ForeignKey
from datetime import datetime, timezone
import enum
from extensions import ma

#enums for different types of actions we want to log in the audit log, 
# this makes it easier to query and analyze logs based on action type
class AuditActionType(enum.Enum):
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILED = "LOGIN_FAILED"
    TRANSACTION_CREATED = "TRANSACTION_CREATED"
    TRANSACTION_ACCEPTED = "TRANSACTION_ACCEPTED"
    TRANSACTION_CANCELLED = "TRANSACTION_CANCELLED"
    OFFER_CREATED = "OFFER_CREATED"
    OFFER_PARTIALLY_FILLED = "OFFER_PARTIALLY_FILLED"
    OFFER_FULLY_FILLED = "OFFER_FULLY_FILLED"
    OFFER_CANCELLED = "OFFER_CANCELLED"
    ALERT_CREATED = "ALERT_CREATED"
    ALERT_DELETED = "ALERT_DELETED"
    PREFERENCE_UPDATED = "PREFERENCE_UPDATED"

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, ForeignKey('user.id'), nullable=True)
    #action type is an enum that specifies the type of action being logged
    action_type = db.Column(Enum(AuditActionType), nullable=False)
    entity_type = db.Column(db.String(32), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)
    description = db.Column(db.Text, nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)  # To store IPv4 or IPv6 addresses
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __init__(self, action_type, description, user_id=None, entity_type=None, entity_id=None, ip_address=None):
        self.action_type = action_type
        self.description = description
        self.user_id = user_id
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.ip_address = ip_address 
        self.timestamp = datetime.now(timezone.utc)  


class AuditLogSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = AuditLog
        include_fk = True
        fields = (
            'id', 
            'user_id', 
            'action_type', 
            'entity_type', 
            'entity_id', 
            'description', 
            'ip_address',
            'timestamp'
            )

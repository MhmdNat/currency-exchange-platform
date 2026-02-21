from model.user import User
from model.userPreferences import UserPreferences
from model.rateAlerts import RateAlerts
from model.transaction import Transaction
from extensions import ma

class UserSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = User
        fields = ('id', 'user_name', 'role', 'status')

class UserPreferencesSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = UserPreferences
        fields = '__all__'

class RateAlertsSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = RateAlerts
        fields = '__all__'

class TransactionSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Transaction
        fields = '__all__'

# Schema instances
user_schema = UserSchema()
users_schema = UserSchema(many=True)
user_preferences_schema = UserPreferencesSchema()
user_preferences_list_schema = UserPreferencesSchema(many=True)
rate_alerts_schema = RateAlertsSchema()
rate_alerts_list_schema = RateAlertsSchema(many=True)
transaction_schema = TransactionSchema()
transactions_schema = TransactionSchema(many=True)

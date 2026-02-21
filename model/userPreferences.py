from sqlalchemy import Column, Integer, String, ForeignKey
from extensions import db
from extensions import ma


class UserPreferences(db.Model):
    __tablename__ = 'user_preferences'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), unique=True, nullable=False)
    default_time_range = Column(String(32), default='3d')  #'1d', '3d', '1w', '1m'
    graph_interval = Column(String(32), default='daily')    #'hourly', 'daily'

#create schema

class UserPreferencesSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = UserPreferences
        include_fk = True
        fields = ("user_id", "default_time_range", "graph_interval")
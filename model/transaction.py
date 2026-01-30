from sqlalchemy.orm import Mapped, mapped_column
from extentions import db, ma
from sqlalchemy import CheckConstraint
from marshmallow import fields
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from datetime import datetime, timezone
from model.user import User

class Transaction(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    usd_amount: Mapped[float] = mapped_column(nullable=False)
    lbp_amount: Mapped[float] = mapped_column(nullable=False)
    usd_to_lbp: Mapped[bool] = mapped_column(nullable=False)
    added_date: Mapped[datetime] = mapped_column(nullable=False)
    user_id: Mapped[int] = mapped_column(db.ForeignKey("user.id"), nullable=True)

    def __init__(self, usd_amount, lbp_amount, usd_to_lbp, user_id):
        super(Transaction, self).__init__(
            usd_amount=usd_amount,
            lbp_amount=lbp_amount, 
            usd_to_lbp=usd_to_lbp,
            user_id=user_id,
            added_date=datetime.now(timezone.utc)
        )



    __table_args__ = (
        CheckConstraint('usd_amount > 0', name='chk_usd_amount'),
        CheckConstraint('lbp_amount > 0', name='chk_lbp_amount'),
    )


# this is used to tell marshmallow what fields to show
class TransactionSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Transaction
        #tell marshmallow to include foreign key
        include_fk=True
        fields = ("id", "usd_amount", "lbp_amount", "usd_to_lbp", "added_date", "user_id")
        
        

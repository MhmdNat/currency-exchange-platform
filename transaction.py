from sqlalchemy.orm import Mapped, mapped_column
from extentions import db, ma
from sqlalchemy import CheckConstraint
from marshmallow import fields
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

class Transaction(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    usd_amount: Mapped[float] = mapped_column(nullable=False)
    lbp_amount: Mapped[float] = mapped_column(nullable=False)
    usd_to_lbp: Mapped[bool] = mapped_column(nullable=False)

    __table_args__ = (
        CheckConstraint('usd_amount > 0', name='chk_usd_amount'),
        CheckConstraint('lbp_amount > 0', name='chk_lbp_amount'),
    )


# this is used to tell marshmallow what fields to show
class TransactionSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Transaction
        fields = ("id", "usd_amount", "lbp_amount", "usd_to_lbp")
        
        

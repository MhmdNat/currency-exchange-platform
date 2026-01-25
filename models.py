from sqlalchemy.orm import Mapped, mapped_column
from app import db
from sqlalchemy import CheckConstraint

class Transaction(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    usd_amount: Mapped[float] = mapped_column(nullable=False)
    lbp_amount: Mapped[float] = mapped_column(nullable=False)
    usd_to_lbp: Mapped[bool] = mapped_column(nullable=False)

    __table_args__ = (
        CheckConstraint('usd_amount > 0', name='chk_usd_amount'),
        CheckConstraint('lbp_amount > 0', name='chk_lbp_amount'),
    )
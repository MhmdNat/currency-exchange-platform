from sqlalchemy.orm import Mapped, mapped_column
from app import db
class Transaction(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    usd_amount: Mapped[float]
    lbp_amount: Mapped[float]
    usd_to_lbp: Mapped[bool]

    def to_dict(self):
        return {
            "id": self.id,
            "usd_amount": self.usd_amount,
            "lbp_amount": self.lbp_amount,
            "usd_to_lbp": self.usd_to_lbp
        }
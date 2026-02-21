from flask import Blueprint, Response, g
from model.trade import TradeSchema
from jwtAuth import jwt_required
from model.transaction import Transaction
from model.trade import Trade
import csv
import io
csvExports_bp = Blueprint('csv_exports', __name__)




trade_schema = TradeSchema()
trades_schema = TradeSchema(many=True)
# CSV export endpoint
@csvExports_bp.route('/export_csv', methods=['GET'])
@jwt_required
def export_csv():
    user_id = g.current_user_id

    # Transactions
    transactions = Transaction.query.filter_by(user_id=user_id).all()


    # Trades (maker and taker as our user)
    trades = Trade.query.filter(
        (Trade.maker_id==user_id) |
        (Trade.taker_id==user_id)
        ).all()
    
    trades_maker =[]
    trades_taker = []

    for trade in trades:
        if trade.maker_id == user_id:
            trades_maker.append(trade)
        if trade.taker_id == user_id:
            trades_taker.append(trade)

    output = io.StringIO()
    writer = csv.writer(output)

    # Write transactions section
    writer.writerow(['Transactions'])
    writer.writerow(['id', 'usd_amount', 'lbp_amount', 'usd_to_lbp', 'added_date', 'user_id'])
    for txn in transactions:
        writer.writerow([
            txn.id,
            txn.usd_amount,
            txn.lbp_amount,
            txn.usd_to_lbp,
            txn.added_date,
        ])


    # Write trades as maker section
    writer.writerow([])
    writer.writerow([])
    writer.writerow(['Trades as Maker'])
    writer.writerow(['id', 'offer_id', 'maker_username', 'taker_username', 'amount_from', 'amount_to', 'executed_rate', 'direction', 'created_at'])
    for trade in trades_maker:
        writer.writerow([
            trade.id,
            trade.offer_id,
            trade.maker_username,
            trade.taker_username,
            trade.amount_from,
            trade.amount_to,
            trade.executed_rate,
            trade.direction,
            trade.created_at
        ])

    # Write trades (taker)
    writer.writerow([])
    writer.writerow(['Trades as Taker'])
    writer.writerow(['id', 'offer_id', 'maker_username', 'taker_username', 'amount_from', 'amount_to', 'executed_rate', 'direction', 'created_at'])
    for trade in trades_taker:
        writer.writerow([
            trade.id,
            trade.offer_id,
            trade.maker_username,
            trade.taker_username,
            trade.amount_from,
            trade.amount_to,
            trade.executed_rate,
            trade.direction,
            trade.created_at
        ])

    output.seek(0)
    return Response(output.getvalue(), mimetype='text/csv', headers={"Content-Disposition": "attachment; filename=export.csv"})

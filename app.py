from flask import Flask, request, abort, jsonify
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)
app.config[
    'SQLALCHEMY_DATABASE_URI'
    ] = 'mysql+pymysql://root:natourroot@127.0.0.1:3306/exchange'

db = SQLAlchemy(app)
from models import Transaction


#get exchange rate
@app.route('/exchangeRate', methods=['GET'])
def get_exchange_rate():

    # transactions retrieved as lists
    usd_to_lbp_transactions = db.session.execute(
        db.select(Transaction).where(Transaction.usd_to_lbp == True)
    ).scalars().all()
    lbp_to_usd_transactions = db.session.execute(
        db.select(Transaction).where(Transaction.usd_to_lbp == False)
    ).scalars().all()

    # list of each transactions rates
    usd_to_lbp_rates = [
        (t.lbp_amount / t.usd_amount) for t in usd_to_lbp_transactions
    ]
    lbp_to_usd_rates = [
        (t.usd_amount / t.lbp_amount) for t in lbp_to_usd_transactions
    ]

    # final rate of each direction
    avg_usd_to_lbp_rate = (
        sum(usd_to_lbp_rates) / len(usd_to_lbp_rates) 
        if usd_to_lbp_rates else None
        )
    avg_lbp_to_usd_rate = (
        sum(lbp_to_usd_rates) / len(lbp_to_usd_rates) 
        if lbp_to_usd_rates else None
        )

    return jsonify({
        "message":"Retrieved average exchange rates",
        "usd_to_lbp":avg_usd_to_lbp_rate,
        "lbp_to_usd":avg_lbp_to_usd_rate
    }), 200


#create transaction
@app.route('/transaction', methods=['POST'])
def add_transaction():
    data = request.json
    usd_amount = data.get("usd_amount")
    lbp_amount = data.get("lbp_amount")
    usd_to_lbp = data.get("usd_to_lbp")

    #if not an instance of boolean return bad req error
    if not isinstance(usd_to_lbp, bool):
        abort(400, "usd_to_lbp must be boolean")

    #validating currency types and returning error if invalid
    try:
        usd_amount=float(usd_amount)
        lbp_amount=float(lbp_amount)

    except (ValueError, TypeError):
        abort(400, "Amounts must be numbers!")

    # here we know that they are correct types need to validate values
    if (
        usd_amount<=0 or
        lbp_amount<=0
        ):
        abort(400, "currency values must be positive")

    #input has been validated, create transaction instance
    t = Transaction(
        usd_amount=usd_amount,
        lbp_amount=lbp_amount,
        usd_to_lbp=usd_to_lbp
    )
    # add to the session and commit the change to save to db
    db.session.add(t)
    db.session.commit()
    return jsonify({
        "message": "Transaction created",
        "status":"201",
        "transaction": t.to_dict()
     }), 201


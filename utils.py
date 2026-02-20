from model.transaction import Transaction
from datetime import timezone, datetime, timedelta

#reusable functions


def get_transactions_by_date(startDate, endDate):
    #adding a day to support same day ops
    endDate = endDate + timedelta(days=1)

    # transactions retrieved as lists
    usd_to_lbp_transactions = Transaction.query.filter(
        Transaction.added_date >= startDate,
        Transaction.added_date < endDate,
        Transaction.usd_to_lbp == True).all()
    
    lbp_to_usd_transactions = Transaction.query.filter(
        Transaction.added_date >= startDate,
        Transaction.added_date < endDate,
        Transaction.usd_to_lbp == False).all()
    print(usd_to_lbp_transactions)
    return (usd_to_lbp_transactions, lbp_to_usd_transactions)


def get_transaction_rates_weighted(usd_to_lbp_transactions, lbp_to_usd_transactions):
    usd_to_lbp_rates = [
        ((t.lbp_amount / t.usd_amount), t.usd_amount) 
        for t in usd_to_lbp_transactions
        if t.usd_amount != 0
    ]
    lbp_to_usd_rates = [
        ((t.lbp_amount / t.usd_amount), t.usd_amount) 
        for t in lbp_to_usd_transactions
        if t.usd_amount !=0
    ]
    return (usd_to_lbp_rates, lbp_to_usd_rates)


def get_weighted_avg_rate(rates_with_weight):
    total_usd=0
    weighted_sum=0
    for r in rates_with_weight:
        #r is tuple rate, usd weight
        rate=r[0]
        usd_weight=r[1]
        total_usd+=usd_weight
        #rate multiplied by its weight
        weighted_sum += rate * usd_weight

    return weighted_sum/total_usd if total_usd != 0 else None

def convert_str_to_time(start_str, end_str):
    #default if parameters not provided correctly
    current_time = datetime.now(timezone.utc)
    three_days_ago = current_time - timedelta(days=3)

    start_time = datetime.fromisoformat(start_str) if start_str else three_days_ago
    end_time = datetime.fromisoformat(end_str) if end_str else current_time

    return start_time, end_time


def extract_timestamps_and_rates(transactions, key_func):
        
        # dictionary where values are lists
        from collections import defaultdict
        grouped = defaultdict(list)
        
        # append the txn to the bucket where hour/day matches and append it to the value list
        for t in transactions:
            grouped[key_func(t)].append(t)
        timestamps = []
        weighted_rates = []

        #sorted keys in increasing order dates
        for ts in sorted(grouped.keys()):
            #transactions of a bucket
            txns = grouped[ts]

            #get rate avg of said bucket
            rates_with_weight = [(t.lbp_amount / t.usd_amount, t.usd_amount) for t in txns]
            weighted_avg = get_weighted_avg_rate(rates_with_weight)

            #append the key
            timestamps.append(str(ts))

            #append the rate
            weighted_rates.append(weighted_avg)
        return timestamps, weighted_rates
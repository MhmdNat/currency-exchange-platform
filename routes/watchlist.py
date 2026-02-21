from flask import Blueprint, request, jsonify, abort, g
from jwtAuth import jwt_required
from extensions import db
from model.watchlist import WatchlistItem, WatchlistItemSchema
from model.rateAlerts import RateAlert

watchlist_bp = Blueprint('watchlist', __name__)

watchlist_item_schema = WatchlistItemSchema()
watchlist_items_schema = WatchlistItemSchema(many=True)

# Add item to watchlist
@watchlist_bp.route('/watchlist', methods=['POST'])
@jwt_required
def add_watchlist_item():
    data = request.json
    if not data:
        abort(400, "INVALID JSON PAYLOAD")

    user_id = g.current_user_id

    item_type = data.get('item_type')
    direction = data.get('direction')
    threshold_rate = data.get('threshold_rate')
    label = data.get('label')
    rate_alert_id = data.get('rate_alert_id')
    # If linking to a rate alert, skip threshold/direction validation
    if rate_alert_id:
        ra = RateAlert.query.filter_by(id=rate_alert_id).first()
        if not ra:
            abort(404, "Linked RateAlert not found")
        if ra.user_id != user_id:
            abort(403, "Forbidden: cannot link to another user's RateAlert")

        direction = ra.direction                
        threshold_rate = ra.threshold_rate
    else:
        # validate item_type before checking direction/threshold
        if item_type not in ['rate_threshold', 'direction']:
            abort(400, "INVALID item_type. Must be 'rate_threshold' or 'direction'")

        # If item_type is rate_threshold, require threshold_rate and direction
        if item_type == 'rate_threshold':
            if direction is None or threshold_rate is None:
                abort(400, "MISSING FIELDS: 'direction' and 'threshold_rate' required for rate_threshold")
            direction = direction.upper()
            if direction not in ['BUY_USD', 'SELL_USD']:
                abort(400, "INVALID direction. Must be BUY_USD or SELL_USD")
            if threshold_rate <= 0:
                abort(400, "INVALID threshold_rate. Must be a positive number")
            try:
                threshold_rate = float(threshold_rate)
            except Exception:
                abort(400, "INVALID threshold_rate. Must be a number")
        # If item_type is direction, require direction only
        if item_type == 'direction':
            if direction is None:
                abort(400, "MISSING FIELD: 'direction' required for direction item")
            direction = direction.upper()
            if direction not in ['BUY_USD', 'SELL_USD']:
                abort(400, "INVALID direction. Must be BUY_USD or SELL_USD")
            threshold_rate = None

    new_item = WatchlistItem(
        user_id=user_id,
        item_type=item_type,
        direction=direction,
        threshold_rate=threshold_rate,
        label=label,
        rate_alert_id=rate_alert_id
    )

    db.session.add(new_item)
    db.session.commit()

    return watchlist_item_schema.jsonify(new_item), 201

# View my watchlist
@watchlist_bp.route('/watchlist', methods=['GET'])
@jwt_required
def get_my_watchlist():
    user_id = g.current_user_id
    items = WatchlistItem.query.filter_by(user_id=user_id).all()
    return watchlist_items_schema.jsonify(items), 200

# Delete item
@watchlist_bp.route('/watchlist/<int:item_id>', methods=['DELETE'])
@jwt_required
def delete_watchlist_item(item_id):
    user_id = g.current_user_id
    item = WatchlistItem.query.filter_by(id=item_id).first()
    if not item:
        abort(404, "Watchlist item not found")
    if item.user_id != user_id:
        abort(403, "Forbidden: You can only delete your own watchlist items")

    db.session.delete(item)
    db.session.commit()
    return '', 204

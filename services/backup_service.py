import json
import os
from datetime import datetime, timezone
from typing import Any

from extensions import db
from model.offer import Offer
from model.rateAlerts import RateAlert
from model.transaction import Transaction
from model.userPreferences import UserPreferences


class BackupService:
    BACKUP_DIR = os.getenv("BACKUP_DIR", "backups")  # directory where backup files are stored
    STATUS_FILE = "status.json"  # file that stores metadata about last backup

    @classmethod
    def create_backup(cls, trigger="manual"):
        cls._ensure_backup_dir()  # make sure backup folder exists

        timestamp = datetime.now(timezone.utc)  # current UTC time
        backup_id = timestamp.strftime("%Y%m%dT%H%M%SZ")  # unique ID based on timestamp
        file_name = f"backup_{backup_id}.json"
        file_path = os.path.join(cls.BACKUP_DIR, file_name)

        # Collect all table data into one structured dictionary
        payload = {
            "backup_id": backup_id,
            "created_at": timestamp.isoformat(),
            "trigger": trigger,  # manual or scheduled trigger
            "data": {
                "user_preferences": cls._dump_preferences(),
                "rate_alerts": cls._dump_rate_alerts(),
                "transactions": cls._dump_transactions(),
                "offers": cls._dump_offers(),
            },
        }

        # Write backup JSON file to disk
        with open(file_path, "w", encoding="utf-8") as file_obj:
            json.dump(payload, file_obj, indent=2)

        # Save summary metadata about this backup
        status = {
            "last_backup_id": backup_id,
            "last_backup_file": file_name,
            "last_backup_at": payload["created_at"],
            "last_backup_trigger": trigger,
            "counts": {
                "user_preferences": len(payload["data"]["user_preferences"]),
                "rate_alerts": len(payload["data"]["rate_alerts"]),
                "transactions": len(payload["data"]["transactions"]),
                "offers": len(payload["data"]["offers"]),
            },
        }

        cls._write_status(status)  # update status.json
        return status

    @classmethod
    def restore_backup(cls, backup_id=None):
        backup_path = cls._resolve_backup_path(backup_id)  # get backup file path

        # Load JSON backup file
        with open(backup_path, "r", encoding="utf-8") as file_obj:
            payload = json.load(file_obj)

        data = payload.get("data", {})

        # Restore each table and count how many records processed
        restored_counts = {
            "user_preferences": cls._restore_preferences(data.get("user_preferences", [])),
            "rate_alerts": cls._restore_rate_alerts(data.get("rate_alerts", [])),
            "transactions": cls._restore_transactions(data.get("transactions", [])),
            "offers": cls._restore_offers(data.get("offers", [])),
        }

        db.session.commit()  # commit all DB changes

        return {
            "restored_from": payload.get("backup_id"),
            "restored_at": datetime.now(timezone.utc).isoformat(),
            "restored_counts": restored_counts,
        }

    @classmethod
    def get_status(cls):
        cls._ensure_backup_dir()
        status_path = os.path.join(cls.BACKUP_DIR, cls.STATUS_FILE)

        # If no backup has been created yet
        if not os.path.exists(status_path):
            return {
                "last_backup_id": None,
                "last_backup_file": None,
                "last_backup_at": None,
                "last_backup_trigger": None,
                "counts": {
                    "user_preferences": 0,
                    "rate_alerts": 0,
                    "transactions": 0,
                    "offers": 0,
                },
            }

        # Otherwise load existing status file
        with open(status_path, "r", encoding="utf-8") as file_obj:
            return json.load(file_obj)

    @classmethod
    def _dump_preferences(cls):
        rows = UserPreferences.query.all()  # fetch all rows
        return [
            {
                "id": row.id,
                "user_id": row.user_id,
                "default_time_range": row.default_time_range,
                "graph_interval": row.graph_interval,
            }
            for row in rows
        ]

    @classmethod
    def _dump_rate_alerts(cls):
        rows = RateAlert.query.all()
        return [
            {
                "id": row.id,
                "user_id": row.user_id,
                "direction": row.direction,
                "threshold_rate": row.threshold_rate,
                "condition": row.condition,
                "is_triggered": row.is_triggered,
                "triggered_at": cls._to_iso(row.triggered_at),  # convert datetime to string
                "created_at": cls._to_iso(row.created_at),
            }
            for row in rows
        ]

    @classmethod
    def _dump_transactions(cls) -> list[dict[str, Any]]:
        rows = Transaction.query.all()
        return [
            {
                "id": row.id,
                "user_id": row.user_id,
                "usd_amount": row.usd_amount,
                "lbp_amount": row.lbp_amount,
                "usd_to_lbp": row.usd_to_lbp,
                "added_date": cls._to_iso(row.added_date),
            }
            for row in rows
        ]

    @classmethod
    def _dump_offers(cls):
        rows = Offer.query.all()
        return [
            {
                "id": row.id,
                "user_id": row.user_id,
                "from_currency": row.from_currency,
                "to_currency": row.to_currency,
                "amount_total": row.amount_total,
                "amount_remaining": row.amount_remaining,
                "exchange_rate": row.exchange_rate,
                "status": row.status,
                "created_at": cls._to_iso(row.created_at),
            }
            for row in rows
        ]

    @classmethod
    def _restore_preferences(cls, records):
        count = 0
        for record in records:
            row = db.session.get(UserPreferences, record.get("id"))  # try to fetch existing row

            if row is None:  # if not found, create new
                row = UserPreferences(user_id=record.get("user_id"))
                if record.get("id") is not None:
                    row.id = record["id"]  # preserve original ID
                db.session.add(row)

            # update fields
            row.user_id = record.get("user_id")
            row.default_time_range = record.get("default_time_range", "3d")
            row.graph_interval = record.get("graph_interval", "daily")

            count += 1

        return count

    @classmethod
    def _restore_rate_alerts(cls, records):
        count = 0
        for record in records:
            row = db.session.get(RateAlert, record.get("id"))

            if row is None:
                row = RateAlert(
                    user_id=record.get("user_id"),
                    direction=record.get("direction"),
                    threshold_rate=record.get("threshold_rate"),
                    condition=record.get("condition"),
                )
                if record.get("id") is not None:
                    row.id = record["id"]
                db.session.add(row)

            row.user_id = record.get("user_id")
            row.direction = record.get("direction")
            row.threshold_rate = record.get("threshold_rate")
            row.condition = record.get("condition")
            row.is_triggered = bool(record.get("is_triggered", False))
            row.triggered_at = cls._parse_dt(record.get("triggered_at"))

            created_at = cls._parse_dt(record.get("created_at"))
            if created_at:
                row.created_at = created_at

            count += 1

        return count

    @classmethod
    def _restore_transactions(cls, records):
        count = 0
        for record in records:
            row = db.session.get(Transaction, record.get("id"))

            if row is None:
                row = Transaction(
                    usd_amount=record.get("usd_amount"),
                    lbp_amount=record.get("lbp_amount"),
                    usd_to_lbp=bool(record.get("usd_to_lbp")),
                    user_id=record.get("user_id"),
                )
                if record.get("id") is not None:
                    row.id = record["id"]
                db.session.add(row)

            row.user_id = record.get("user_id")
            row.usd_amount = record.get("usd_amount")
            row.lbp_amount = record.get("lbp_amount")
            row.usd_to_lbp = bool(record.get("usd_to_lbp"))

            added_date = cls._parse_dt(record.get("added_date"))
            if added_date:
                row.added_date = added_date

            count += 1

        return count

    @classmethod
    def _restore_offers(cls, records):
        count = 0
        for record in records:
            row = db.session.get(Offer, record.get("id"))

            if row is None:
                row = Offer(
                    user_id=record.get("user_id"),
                    from_currency=record.get("from_currency"),
                    to_currency=record.get("to_currency"),
                    amount_total=record.get("amount_total"),
                    exchange_rate=record.get("exchange_rate"),
                )
                if record.get("id") is not None:
                    row.id = record["id"]
                db.session.add(row)

            row.user_id = record.get("user_id")
            row.from_currency = record.get("from_currency")
            row.to_currency = record.get("to_currency")
            row.amount_total = record.get("amount_total")
            row.amount_remaining = record.get("amount_remaining")
            row.exchange_rate = record.get("exchange_rate")
            row.status = record.get("status", "OPEN")

            created_at = cls._parse_dt(record.get("created_at"))
            if created_at:
                row.created_at = created_at

            count += 1

        return count

    @classmethod
    def _resolve_backup_path(cls, backup_id):
        cls._ensure_backup_dir()

        if backup_id:
            requested_path = os.path.join(cls.BACKUP_DIR, f"backup_{backup_id}.json")
            if not os.path.exists(requested_path):
                raise FileNotFoundError(f"Backup '{backup_id}' not found")
            return requested_path

        # find latest backup file if no ID provided
        files = [
            file_name for file_name in os.listdir(cls.BACKUP_DIR)
            if file_name.startswith("backup_") and file_name.endswith(".json")
        ]

        if not files:
            raise FileNotFoundError("No backups available")

        files.sort(reverse=True)  # newest file first
        return os.path.join(cls.BACKUP_DIR, files[0])

    @classmethod
    def _write_status(cls, status):
        cls._ensure_backup_dir()
        status_path = os.path.join(cls.BACKUP_DIR, cls.STATUS_FILE)
        with open(status_path, "w", encoding="utf-8") as file_obj:
            json.dump(status, file_obj, indent=2)

    @classmethod
    def _ensure_backup_dir(cls) -> None:
        os.makedirs(cls.BACKUP_DIR, exist_ok=True)  # create directory if missing

    @staticmethod
    def _to_iso(value=None) -> str | None:
        if value is None:
            return None
        return value.isoformat()  # convert datetime to ISO string

    @staticmethod
    def _parse_dt(value= None):
        if not value:
            return None
        return datetime.fromisoformat(value)  # convert ISO string back to datetime

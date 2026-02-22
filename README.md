# 430L Backend API

Backend service for USD/LBP exchange, transactions, P2P offers, alerts, watchlist, notifications, admin analytics, and backup/restore.

## 1. Backend Source Code and Dependencies

### Source code structure
- `app.py`: Flask app entrypoint, blueprint registration, scheduler startup.
- `routes/`: User-facing API routes.
- `routes/admin/`: Admin-only routes.
- `model/`: SQLAlchemy models.
- `services/`: Service layer (`rate_service.py`, `backup_service.py`).
- `utils.py`: Shared helpers and validations.
- `extensions.py`: Shared Flask extension instances.
- `jwtAuth.py`: JWT creation and decorators.

### Dependencies
All Python dependencies are listed in `requirements.txt`.

Install with:
```powershell
pip install -r requirements.txt
```

## 2. Environment Setup

### Prerequisites
- Python 3.10+
- MySQL server
- `pip`

### Create and activate virtual environment (Windows PowerShell)
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### Install dependencies
```powershell
pip install -r requirements.txt
```

## 3. Database Configuration

This project reads DB settings from environment variables via `.env` (loaded in `db_config.py`).

Create a `.env` file in the project root:
```env
DB_USER=your_mysql_user
DB_PASSWORD=your_mysql_password
DB_HOST=localhost
DB_PORT=3306
DB_NAME=your_database_name
SECRET_KEY=your_jwt_secret_key
BACKUP_DIR=backups
```

### Notes
- DB URI is built as:
  - `mysql+pymysql://DB_USER:DB_PASSWORD@DB_HOST:DB_PORT/DB_NAME`
- `SECRET_KEY` is required for JWT signing/verification.
- `BACKUP_DIR` is optional (defaults to `backups`).

## 4. Run the Server

Either
```powershell
set FLASK_APP=app.py
set FLASK_ENV=development
flask run
```

Default local URL:
- `http://127.0.0.1:5000`


or

Alternative:
```powershell
python app.py
```

## 5. How to Test Endpoints

You can test with Postman or curl.

### 5.1 Quick Auth Flow (required for protected endpoints)

1. Register user
- `POST /user`
```json
{
  "user_name": "alice",
  "password": "StrongPass123"
}
```

2. Login
- `POST /auth/login` (or `/authentication`)
```json
{
  "user_name": "alice",
  "password": "StrongPass123"
}
```

3. Copy returned token and send in header:
```http
Authorization: Bearer <TOKEN>
```

### 5.2 Postman testing checklist
- Create a collection and set `baseUrl = http://127.0.0.1:5000`.
- Test public endpoints first:
  - `GET {{baseUrl}}/exchangeRate`
  - `GET {{baseUrl}}/exchangeRate/analytics`
  - `GET {{baseUrl}}/exchangeRate/history`
- Then authenticated endpoints (with Bearer token):
  - `GET {{baseUrl}}/transaction`
  - `POST {{baseUrl}}/transaction`
  - `POST {{baseUrl}}/offers`
  - `GET {{baseUrl}}/notifications`
  - `GET {{baseUrl}}/audit-logs`
- For admin endpoints, login as an ADMIN user and test:
  - `GET {{baseUrl}}/admin/users`
  - `GET {{baseUrl}}/admin/analytics/transaction-volume`
  - `POST {{baseUrl}}/admin/backup`

### 5.3 Example curl commands

Register:
```bash
curl -X POST http://127.0.0.1:5000/user \
  -H "Content-Type: application/json" \
  -d '{"user_name":"alice","password":"StrongPass123"}'
```

Login:
```bash
curl -X POST http://127.0.0.1:5000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user_name":"alice","password":"StrongPass123"}'
```

Create transaction (replace token):
```bash
curl -X POST http://127.0.0.1:5000/transaction \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{"usd_amount":100,"lbp_amount":0,"usd_to_lbp":true}'
```

## 6. Main Endpoint Groups

- Auth: `/user`, `/auth/login`, `/authentication`
- Exchange: `/exchangeRate`, `/exchangeRate/analytics`, `/exchangeRate/history`
- Transactions: `/transaction`, `/transactions`
- Marketplace: `/offers`, `/offers/<id>/accept`, `/market/offers/<id>/accept`, `/trades`
- Alerts: `/rateAlerts`
- Watchlist: `/watchlist`
- Preferences: `/preferences`
- Notifications: `/notifications`
- CSV Export: `/export_csv`
- Logs: `/audit-logs`
- Admin: `/admin/*` (users, analytics, rates, backups, moderation)

## 7. Important Notes

- Some critical endpoints are rate-limited.
- Scheduler starts with the app and runs:
  - alert checks every 60 seconds
  - automated backups every 6 hours
- Keep `.env` out of version control.
- Backup files are generated under `backups/`.

## 8. Troubleshooting

- `401 Unauthorized`:
  - Missing/invalid/expired token.
- `403 Forbidden`:
  - User lacks role/permission or account is suspended/banned.
- `503 Service Unavailable` on transaction:
  - Latest rate missing or flagged as anomaly.
- DB connection errors:
  - Verify `.env` values and MySQL service status.

# MTC Assistant Web Dashboard

## Architecture

The dashboard is a separate Next.js service under `dashboard/`. The LINE bot remains a Flask service under `src/mtc_assistant/`.

```
Browser
  -> Next.js dashboard
  -> Next.js /api/admin/* proxy
  -> Flask /api/admin/* blueprint
  -> Sustainability Analytics Layer
  -> Firestore / LINE Messaging API / Gemini Vision / bot metrics
```

This keeps dashboard failures out of the LINE webhook path. The browser never receives `MTC_DASHBOARD_API_TOKEN`; only the Next.js server uses it when proxying to Flask.

## Environment Variables

Set these on both services where noted:

- Flask bot service: `MTC_DASHBOARD_API_TOKEN`
- Flask bot service: `DASHBOARD_ALLOWED_ORIGINS`
- Next.js dashboard service: `MTC_BOT_API_BASE_URL`
- Next.js dashboard service: `MTC_DASHBOARD_API_TOKEN`
- Next.js dashboard service: `DASHBOARD_PASSWORD`
- Next.js dashboard service: `DASHBOARD_SESSION_SECRET`

Use a long random value for both token and session secret. Do not reuse LINE, Gemini, or Firebase secrets.

## Local Development

Run the Flask bot:

```powershell
$env:PYTHONPATH="src"
$env:MTC_DASHBOARD_API_TOKEN="local-dashboard-token"
python -m mtc_assistant.main
```

Run the dashboard:

```powershell
cd dashboard
$env:MTC_BOT_API_BASE_URL="http://127.0.0.1:5001"
$env:MTC_DASHBOARD_API_TOKEN="local-dashboard-token"
$env:DASHBOARD_PASSWORD="local-password"
$env:DASHBOARD_SESSION_SECRET="replace-with-long-local-secret"
npm run dev
```

Open `http://localhost:3000`.

## API Contract

Flask exposes token-protected endpoints:

- `GET /api/admin/overview`
- `GET /api/admin/sustainability`
- `POST /api/admin/paperless-capture`
- `GET /api/admin/users?limit=100&offset=0`
- `GET /api/admin/homeworks?limit=30`
- `GET /api/admin/broadcasts?limit=20`
- `POST /api/admin/broadcasts`
- `GET /api/admin/blacklist`
- `POST /api/admin/blacklist`
- `DELETE /api/admin/blacklist/<user_id>`

`/api/admin/sustainability` estimates classroom impact from existing counts:

```text
paper_saved_sheets = (homework_count + broadcast_count) * active_students
admin_minutes_saved = total_requests + homework_count * 3 + broadcast_count * max(active_students - 1, 0) * 0.5
co2_saved_grams = paper_saved_sheets * PAPER_CO2_GRAMS_PER_SHEET
equal_access_rate_percent = active_students / MTC_EXPECTED_CLASS_SIZE * 100
```

`/api/admin/paperless-capture` accepts `multipart/form-data` field `image` or JSON `image_base64` with `mime_type`. It returns a Gemini Vision summary for proposal screenshots and stores capture history when Firestore is available.

Errors use:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "request_id": ""
  }
}
```

## Verification

```powershell
python -m compileall -q src
cd dashboard
npm run lint
npm run typecheck
npm run build
npm audit --audit-level=moderate
```

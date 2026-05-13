# MTC Assistant VPS Migration Plan

This document describes how to validate MTC Assistant locally with Docker Desktop now, then deploy it beside KwanNurse-Bot on an Oracle Cloud Ubuntu ARM VPS later.

## Architecture Summary

- **Runtime**: Python 3.11, Flask, Gunicorn.
- **Container port**: `5000`.
- **Host port for MTC Assistant**: `5001` to avoid conflict with KwanNurse-Bot on `5000`.
- **Gunicorn worker class**: `gthread` only.
- **Gunicorn workers**: `1` while GPA sessions, Smart Calc variables, and blacklist cache are in process memory.
- **External state**: Firebase Firestore for persistent data and blacklist source of truth.
- **Webhook endpoint**: `/callback`.
- **Health endpoint**: `/healthz`.

## Part 1 — Right Now: Local Docker Desktop Testing

### 1. Prepare local environment

1. Copy `.env.example` to `.env`.
2. Fill in real values for:
   - `CHANNEL_ACCESS_TOKEN`
   - `CHANNEL_SECRET`
   - `GEMINI_API_KEY_PRIMARY`
   - `GEMINI_API_KEY_SECONDARY` if used
   - `ADMIN_USER_IDS`
   - one Firebase credential option: `FIREBASE_CREDENTIALS_JSON` or `FIREBASE_CREDENTIALS_BASE64`
3. Keep `PORT=5000` inside `.env`; Compose maps it to host port `5001`.
4. Do not commit `.env` or Firebase key files.

### 2. Build and start locally

```powershell
docker compose build
docker compose up -d
```

Check logs:

```powershell
docker compose logs -f mtc-assistant
```

Expected signs:

- Gunicorn starts with `gthread`.
- The app binds to `0.0.0.0:5000` inside the container.
- Firebase logs `Firebase Connected Successfully` if credentials and Firestore access are correct.
- Blacklist logs show it loaded from Firebase.

### 3. Validate health and status endpoints

Open these in a browser or use PowerShell:

```powershell
Invoke-RestMethod http://localhost:5001/
Invoke-RestMethod http://localhost:5001/healthz
Invoke-RestMethod http://localhost:5001/metrics
Invoke-RestMethod http://localhost:5001/stats
```

Notes:

- `/healthz` returns `200` only when LINE config is present.
- Firebase can initially show disconnected while the background connection is still starting.
- Re-check logs if Firebase remains disconnected.

### 4. Test LINE webhook locally

For real LINE webhook testing from your phone, expose local port `5001` with a tunnel such as Cloudflare Tunnel or ngrok, then set LINE webhook URL to:

```text
https://your-temporary-tunnel-domain/callback
```

After testing, change the LINE webhook back to Render or the final VPS domain when ready.

### 5. Stateful feature checklist

Test these from LINE after the local webhook is connected:

- **GPA session**:
  - Send `เริ่ม GPA`
  - Send `เพิ่มวิชา คณิต 3 4`
  - Send `ดู GPA`
  - Send `คำนวณ GPA`
- **Smart Calc variables**:
  - Send `คำนวณ x = 5`
  - Send `คำนวณ x * 2`
  - Send `คำนวณ vars`
  - Send `คำนวณ clearvars`
- **Blacklist cache**:
  - As an admin, test ban/list/unban commands.
  - Restart the container and confirm blacklist data reloads from Firestore.
- **Firebase reconnect behavior**:
  - Confirm `/healthz` does not hang even if Firebase is slow.
- **Gemini fallback**:
  - Test an AI prompt and confirm primary/fallback model behavior in logs.

### 6. Stop local stack

```powershell
docker compose down
```

To rebuild after Dockerfile or dependency changes:

```powershell
docker compose up -d --build
```

## Part 2 — In 2 Days: Oracle VPS Deployment Beside KwanNurse-Bot

### 1. Prepare the VPS

On the Ubuntu ARM VPS, install or verify:

- Docker Engine
- Docker Compose plugin
- Git
- Caddy
- Firewall rules for `80` and `443`

Keep KwanNurse-Bot running on host port `5000`. MTC Assistant should use host port `5001`.

### 2. Clone and configure MTC Assistant

```bash
git clone <your-mtc-assistant-repo-url> mtc-assistant
cd mtc-assistant
cp .env.example .env
nano .env
```

Set production secrets in `.env`:

- LINE production channel token and secret
- Gemini API keys
- Firebase credentials, preferably `FIREBASE_CREDENTIALS_BASE64`
- `ADMIN_USER_IDS`
- `PORT=5000`
- `FLASK_DEBUG=false`
- `DEBUG=false`

### 3. Start the container

```bash
docker compose up -d --build
```

Verify locally on the VPS:

```bash
curl http://127.0.0.1:5001/healthz
curl http://127.0.0.1:5001/
docker compose logs -f mtc-assistant
```

### 4. Configure Caddy reverse proxy

Example Caddyfile with separate hostnames:

```caddyfile
kwannurse.example.com {
    reverse_proxy 127.0.0.1:5000
}

mtc.example.com {
    reverse_proxy 127.0.0.1:5001
}
```

If both bots must share one domain, use separate paths only if LINE webhook routing and each app support the path design. Separate subdomains are cleaner and safer.

Reload Caddy:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

### 5. Update LINE webhook

Set MTC Assistant's LINE webhook URL to:

```text
https://mtc.example.com/callback
```

Then verify the webhook in the LINE Developers Console.

### 6. Production validation checklist

- **Container**: `docker ps` shows `mtc-assistant` healthy.
- **Health**: `https://mtc.example.com/healthz` returns healthy or degraded with LINE configured.
- **Logs**: no repeated Firebase credential or gRPC errors.
- **LINE**: webhook verification succeeds.
- **Stateful features**: GPA sessions and Smart Calc variables work across multi-message flows.
- **Admin features**: blacklist and broadcast/impersonate features initialize as expected.
- **Co-hosting**: KwanNurse-Bot remains reachable and port `5000` is not reused by MTC Assistant.

## Operational Notes

- Keep `--workers 1` until state is moved to Firestore, Redis, or another shared store.
- Keep `gthread`; do not switch to `gevent` because Firebase gRPC can deadlock or behave unpredictably.
- Avoid `--preload` for the containerized command so Firebase/gRPC clients initialize inside the worker process.
- Store real secrets only in `.env` on the VPS or in a secure secret manager.
- Back up `.env` securely before replacing or rebuilding the VPS.

## Useful Commands

```bash
docker compose ps
docker compose logs -f mtc-assistant
docker compose restart mtc-assistant
docker compose pull
docker compose up -d --build
```

# -*- coding: utf-8 -*-
"""
MTC Assistant v.21 (Optimized Edition)
Main entry point with Flask routes and initialization

Improvements:
- Added broadcast system initialization
- Added impersonate feature initialization
- Connection pooling
- Response caching
- Enhanced error handling
- Performance monitoring
"""

import os
import threading

import warnings
warnings.filterwarnings('ignore', category=UserWarning, module='pydantic')

import datetime
import time
from flask import Flask, request, abort, jsonify, g

# Firebase imports
import firebase_admin
from firebase_admin import credentials, firestore

# Gemini imports (google-genai)
from google import genai

# LINE imports
from linebot.v3.exceptions import InvalidSignatureError

# Import from our modules
from config import (
    logger, setup_logging, validate_config,
    PORT, FLASK_DEBUG, ACCESS_TOKEN, CHANNEL_SECRET,
    GEMINI_API_KEY_V3, GEMINI_API_KEY_V25,
    FIREBASE_KEY_PATH,
    GEMINI_MODEL_V3, GEMINI_MODEL_V25,
    LOCAL_TZ
)

from handlers import handler

import features  # Import features module to set global variables
import broadcast  # Import broadcast module

# ============================================================================
# FLASK APP INITIALIZATION
# ============================================================================
app = Flask(__name__)

# Setup logging
setup_logging()
app.logger.handlers = logger.handlers
app.logger.setLevel(logger.level)

# Validate configuration
validate_config()

# ============================================================================
# PERFORMANCE MONITORING
# ============================================================================
_metrics_lock = threading.Lock()
_metrics = {
    "total_requests": 0,
    "total_errors": 0,
    "total_response_time": 0.0,
    "cache_hits": 0,
    "cache_misses": 0,
    "start_time": time.time(),
}


def _increment_metric(key: str, value: float = 1) -> None:
    """Thread-safe counter increment for _metrics."""
    with _metrics_lock:
        _metrics[key] += value


@app.before_request
def before_request():
    """Log request start time."""
    g.start_time = time.time()
    with _metrics_lock:
        _metrics["total_requests"] += 1


@app.after_request
def after_request(response):
    """Log response time and update metrics."""
    if hasattr(g, 'start_time'):
        elapsed = (time.time() - g.start_time) * 1000
        with _metrics_lock:
            _metrics["total_response_time"] += elapsed

        if elapsed > 1000:
            logger.warning(f"Slow request to {request.path}: {elapsed:.2f}ms")
        else:
            logger.debug(f"Request to {request.path}: {elapsed:.2f}ms")

    return response

# ============================================================================
# FIREBASE INITIALIZATION
# ============================================================================
db = None
try:
    if os.path.exists(FIREBASE_KEY_PATH):
        if not firebase_admin._apps:
            cred = credentials.Certificate(FIREBASE_KEY_PATH)
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        features.set_database(db)  # Set database in features module
        broadcast.set_database(db)  # Set database in broadcast module
        from user_blacklist import get_blacklist_manager
        _bm = get_blacklist_manager()
        _bm.db = db
        _bm.load_blacklist()
        logger.info("🚫 Blacklist loaded from Firebase")
        logger.info("🔥 Firebase Connected Successfully!")
    else:
        logger.warning(f"⚠️ Missing {FIREBASE_KEY_PATH}. Homework DB features will be disabled.")
except Exception as e:
    logger.exception(f"❌ Firebase Init Error: {e}")

# ============================================================================
# GEMINI AI INITIALIZATION (google-genai client)
# ============================================================================
gemini_client_v3 = None
gemini_client_v25 = None

try:
    if GEMINI_API_KEY_V3:
        gemini_client_v3 = genai.Client(api_key=GEMINI_API_KEY_V3)
        logger.info(f"🤖 Gemini primary client created for model '{GEMINI_MODEL_V3}'")

    if GEMINI_API_KEY_V25:
        gemini_client_v25 = genai.Client(api_key=GEMINI_API_KEY_V25)
        logger.info(f"🤖 Gemini secondary client created for model '{GEMINI_MODEL_V25}'")

    # ส่งทั้ง client และชื่อโมเดลไปให้ features
    features.set_gemini_models(
        client_primary=gemini_client_v3,
        model_primary=GEMINI_MODEL_V3,
        client_fallback=gemini_client_v25,
        model_fallback=GEMINI_MODEL_V25,
    )

except Exception as e:
    logger.error(f"❌ Gemini model init failed: {e}")

# ============================================================================
# LINE API INITIALIZATION (for Broadcast + Impersonate)
# ============================================================================
from linebot.v3.messaging import Configuration as LineConfig
line_config = LineConfig(access_token=ACCESS_TOKEN) if ACCESS_TOKEN else None

if line_config:
    # Initialize broadcast
    broadcast.set_line_api(line_config)
    logger.info("📢 Broadcast system initialized")
    
    # Initialize impersonate (NEW!)
    try:
        from admin_impersonate import set_line_api as set_impersonate_line_api
        set_impersonate_line_api(line_config)
        logger.info("🎭 Impersonate feature initialized")
    except ImportError:
        logger.warning("⚠️ admin_impersonate.py not found - impersonate feature disabled")

# ============================================================================
# FLASK ROUTES
# ============================================================================

@app.route("/callback", methods=['POST'])
def callback():
    """Handle LINE webhook callback"""
    signature = request.headers.get('X-Line-Signature') or request.headers.get('x-line-signature')
    if not signature:
        logger.error("Missing X-Line-Signature header.")
        with _metrics_lock:
            _metrics["total_errors"] += 1
        abort(400)

    body = request.get_data(as_text=True)
    logger.debug("Request body: %s", body[:200])

    if handler is None:
        logger.error("Webhook handler not configured (missing CHANNEL_SECRET).")
        with _metrics_lock:
            _metrics["total_errors"] += 1
        abort(500)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("Invalid signature. Check CHANNEL_SECRET.")
        with _metrics_lock:
            _metrics["total_errors"] += 1
        abort(400)
    except Exception as e:
        logger.exception("Error handling request: %s", e)
        with _metrics_lock:
            _metrics["total_errors"] += 1
        abort(500)

    return "OK", 200

@app.route("/", methods=['GET'])
def home():
    """Health check and status endpoint"""
    cfg_ok = "OK" if ACCESS_TOKEN and CHANNEL_SECRET else "CONFIG_MISSING"
    gemini_status = "OK" if (GEMINI_API_KEY_V3 or GEMINI_API_KEY_V25) else "MISSING"
    db_status = "OK" if db else "DISCONNECTED"
    broadcast_status = "OK" if line_config else "DISABLED"

    uptime = int(time.time() - _metrics["start_time"])

    return (
        f"🤖 MTC Assistant v21 (Optimized + Impersonate Edition)\n\n"
        f"Status:\n"
        f"  LINE: {cfg_ok}\n"
        f"  Gemini AI: {gemini_status}\n"
        f"  Firebase: {db_status}\n"
        f"  Broadcast: {broadcast_status}\n\n"
        f"Performance:\n"
        f"  Uptime: {uptime}s\n"
        f"  Total Requests: {_metrics['total_requests']}\n"
        f"  Total Errors: {_metrics['total_errors']}\n"
        f"  Avg Response Time: {_metrics['total_response_time'] / max(_metrics['total_requests'], 1):.2f}ms\n\n"
        f"Endpoints:\n"
        f"  /callback - LINE webhook\n"
        f"  /healthz - Health check (JSON)\n"
        f"  /metrics - Performance metrics\n"
        f"  /stats - Bot statistics\n"
    )

@app.route("/healthz", methods=['GET'])
def healthz():
    """Enhanced health check endpoint with connectivity test"""
    start_time = time.time()

    services_status = {
        "line": bool(ACCESS_TOKEN and CHANNEL_SECRET),
        "gemini": bool((GEMINI_API_KEY_V3 or GEMINI_API_KEY_V25) and (gemini_client_v3 or gemini_client_v25)),
        "firebase": bool(db),
        "broadcast": bool(line_config),
    }

    # Test Firebase connectivity
    if db:
        try:
            list(db.collection('health_check').limit(1).stream())
            services_status["firebase_connectivity"] = True
        except Exception as e:
            logger.warning(f"Firebase connectivity test failed: {e}")
            services_status["firebase_connectivity"] = False

    response_time = (time.time() - start_time) * 1000  # ms

    # Determine overall health
    all_critical_ok = services_status["line"] and services_status["firebase"]
    status_code = 200 if all_critical_ok else 503

    return jsonify({
        "status": "healthy" if all_critical_ok else "degraded",
        "version": "21-optimized-impersonate",
        "response_time_ms": round(response_time, 2),
        "timestamp": datetime.datetime.now(tz=LOCAL_TZ).isoformat(),
        "services": services_status
    }), status_code

@app.route("/metrics", methods=['GET'])
def metrics():
    """Prometheus-style metrics endpoint"""
    uptime = time.time() - _metrics["start_time"]
    avg_response_time = _metrics['total_response_time'] / max(_metrics['total_requests'], 1)
    error_rate = (_metrics['total_errors'] / max(_metrics['total_requests'], 1)) * 100

    return jsonify({
        "uptime_seconds": round(uptime, 2),
        "total_requests": _metrics["total_requests"],
        "total_errors": _metrics["total_errors"],
        "error_rate_percent": round(error_rate, 2),
        "avg_response_time_ms": round(avg_response_time, 2),
        "cache_hits": _metrics["cache_hits"],
        "cache_misses": _metrics["cache_misses"],
        "cache_hit_rate_percent": round(
            (_metrics["cache_hits"] / max(_metrics["cache_hits"] + _metrics["cache_misses"], 1)) * 100,
            2
        )
    }), 200

@app.route("/stats", methods=['GET'])
def stats():
    """Show bot statistics"""
    try:
        from handlers import _user_message_history
        total_users = len(_user_message_history)
        total_messages = sum(len(msgs) for msgs in _user_message_history.values())
    except (ImportError, AttributeError) as e:
        logger.warning(f"Could not read _user_message_history from handlers: {e}")
        total_users = -1
        total_messages = -1

    broadcast_stats = {}
    if db:
        try:
            broadcast_stats = {"registered_users": broadcast.get_user_count()}
        except Exception as e:
            logger.warning(f"Could not get broadcast stats: {e}")

    return jsonify({
        "total_users": total_users,
        "total_messages": total_messages,
        "rate_limit_tracked_users": total_users,
        **broadcast_stats
    }), 200

# ============================================================================
# ERROR HANDLERS
# ============================================================================
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        "error": "Not Found",
        "message": "The requested endpoint does not exist",
        "available_endpoints": ["/", "/callback", "/healthz", "/metrics", "/stats"]
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {error}")
    with _metrics_lock:
        _metrics["total_errors"] += 1
    return jsonify({
        "error": "Internal Server Error",
        "message": "An unexpected error occurred. Please try again later."
    }), 500

@app.errorhandler(503)
def service_unavailable(error):
    """Handle 503 errors"""
    logger.error(f"Service unavailable: {error}")
    return jsonify({
        "error": "Service Unavailable",
        "message": "The service is temporarily unavailable. Please try again later."
    }), 503

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================
def print_startup_banner():
    """Print startup banner with configuration info"""
    banner = """
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║      🤖 MTC Assistant v21 (Optimized + Impersonate)      ║
║                                                           ║
║  Performance Enhanced - Production Ready                 ║
║  NEW: Admin Impersonate Feature 🎭                       ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
"""
    logger.info(banner)

    # เช็กสถานะ Gemini
    gemini_ready = bool(gemini_client_v3 or gemini_client_v25)

    logger.info("Configuration:")
    logger.info(f"  • Port: {PORT}")
    logger.info(f"  • Debug Mode: {FLASK_DEBUG}")
    logger.info(f"  • LINE Bot: {'✅ Configured' if ACCESS_TOKEN and CHANNEL_SECRET else '❌ Not configured'}")
    logger.info(f"  • Gemini AI: {'✅ Ready' if gemini_ready else '❌ Disabled'}")
    logger.info(f"  • Firebase: {'✅ Connected' if db else '❌ Disconnected'}")
    logger.info(f"  • Broadcast: {'✅ Initialized' if line_config else '❌ Disabled'}")
    logger.info("")
    logger.info("Features:")
    logger.info("  ⚡ Response caching")
    logger.info("  ⚡ Connection pooling")
    logger.info("  ⚡ Performance monitoring")
    logger.info("  ⚡ Enhanced error handling")
    logger.info("  🎭 Admin impersonate feature (NEW!)")
    logger.info("")
    logger.info("Module Structure:")
    logger.info("  📁 config.py             - Configuration & Constants")
    logger.info("  📁 features.py           - Feature Functions")
    logger.info("  📁 handlers.py           - LINE Handlers & Routing")
    logger.info("  📁 broadcast.py          - Broadcast System")
    logger.info("  📁 admin_impersonate.py  - Impersonate Feature (NEW!)")
    logger.info("  📁 main.py               - Flask App (this file)")
    logger.info("")
    logger.info("🚀 Server starting...")
    logger.info("=" * 60)

if __name__ == "__main__":
    # Print the banner FIRST so any hang during Firebase / Gemini init is
    # immediately visible in the console rather than producing silent delay.
    print_startup_banner()

    # Run Flask app
    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=FLASK_DEBUG,
        threaded=True  # Enable threading for better performance
    )
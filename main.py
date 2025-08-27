import os
from logging_setup import configure_logging

# Initialize minimal logging before importing app
configure_logging(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    use_json=os.getenv("USE_MINIMAL_LOGGING", "true").lower() == "true"
)

from app import app  # noqa: F401

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)

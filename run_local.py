"""
Simple Flask app runner that loads .env file before starting.
"""
from dotenv import load_dotenv
import os

# Load environment variables from .env file
print("Loading environment from .env file...")
load_dotenv()

# Verify key variables are loaded
required_vars = [
    "SESSION_SECRET",
    "OPENAI_API_KEY",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET"
]

print("\nChecking required environment variables:")
missing = []
for var in required_vars:
    value = os.getenv(var)
    if value:
        print(f"✅ {var}: {value[:20]}... (loaded)")
    else:
        print(f"❌ {var}: NOT SET")
        missing.append(var)

if missing:
    print(f"\n⚠️  Warning: Missing variables: {', '.join(missing)}")
    print("Some features may not work correctly.")
else:
    print("\n✅ All required variables loaded!")

print("\nStarting Flask app...\n")
print("="*80)

# Now import and run the app
from app import app

if __name__ == '__main__':
    # Run in debug mode for local development
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=False  # Avoid double-loading with dotenv
    )

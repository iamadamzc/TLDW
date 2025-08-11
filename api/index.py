import os
import sys

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

# Add a health check endpoint
@app.route('/api/health')
def health_check():
    return {
        'status': 'healthy',
        'message': 'TL;DW API is running',
        'watch_later_fix': 'active'
    }

# This is the WSGI entry point for Vercel
# Vercel will call this app directly
app = app

# For local testing
if __name__ == "__main__":
    app.run(debug=False)
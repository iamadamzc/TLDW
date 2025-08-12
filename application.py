#!/usr/bin/env python3
"""
Elastic Beanstalk entry point for TL;DW application
"""
from app import app

# Elastic Beanstalk looks for an 'application' callable by default
application = app

if __name__ == "__main__":
    application.run(debug=False)
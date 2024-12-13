# This file contains environment variables for Flask application configuration
# WARNING: No secrets, API keys, or credentials should be stored in this file
# For production, use secure environment variables for sensitive configurations

# Flask Application Entry Point
# Specifies the path to the main application module
FLASK_APP=src/main.py

# Flask Environment Mode
# Controls application behavior and features
# Values: development, production
# SECURITY NOTE: Must be set to 'production' in production environment
FLASK_ENV=development

# Flask Debug Mode
# Enables detailed error pages and hot reloading
# Values: 0 (disabled), 1 (enabled)
# SECURITY NOTE: Must be disabled (0) in production environment
FLASK_DEBUG=1

# Application Host Configuration
# Specifies the host address to bind the application
# Default: 0.0.0.0 (all interfaces)
HOST=0.0.0.0

# Application Port Configuration
# Specifies the port number for the application to listen on
# Must be between 1024-65535
PORT=8000

# Gunicorn Worker Configuration
# Number of worker processes for handling requests
# Should be adjusted based on available CPU cores in production
# Formula: (2 x NUM_CORES) + 1
GUNICORN_WORKERS=1
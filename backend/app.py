"""
app.py — Flask application entry point.

Registers all API blueprints, configures CORS, and starts the dev server.
The compiler engine and ML advisor are completely independent of Flask;
this file only wires them to HTTP routes.

Phase 6: Full pipeline wired — /api/analyze, /api/tokenize, /api/model live.
"""

import os
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from api.routes import api_blueprint
import config


def create_app() -> Flask:
    """Application factory — creates and configures the Flask app."""
    frontend_new_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend_new", "dist"))
    legacy_frontend = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
    frontend_dir = frontend_new_dist if os.path.exists(frontend_new_dist) else legacy_frontend
    
    app = Flask(__name__, static_folder=frontend_dir, static_url_path="")
    app.config["DEBUG"] = config.FLASK_DEBUG

    # Allow all origins during development
    CORS(app, resources={r"/*": {"origins": "*"}})

    # Register the main API blueprint under /api
    app.register_blueprint(api_blueprint, url_prefix="/api")

    # ----------------------------------------------------------------
    # Frontend static file routes
    # ----------------------------------------------------------------
    @app.route("/")
    def serve_index():
        return send_from_directory(frontend_dir, "index.html")

    @app.route("/<path:path>")
    def serve_static(path):
        target = os.path.join(frontend_dir, path)
        if os.path.exists(target) and os.path.isfile(target):
            return send_from_directory(frontend_dir, path)
        # For single page apps, fallback to index.html if file not found
        if os.path.exists(os.path.join(frontend_dir, "index.html")):
            return send_from_directory(frontend_dir, "index.html")
        return jsonify({"success": False, "error": "File not found."}), 404

    # ----------------------------------------------------------------
    # Global error handlers
    # ----------------------------------------------------------------
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"success": False, "error": "Endpoint not found."}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"success": False, "error": "Method not allowed."}), 405

    @app.errorhandler(413)
    def payload_too_large(e):
        return jsonify({"success": False, "error": "Request payload too large."}), 413

    @app.errorhandler(415)
    def unsupported_media(e):
        return jsonify({"success": False, "error": "Content-Type must be application/json."}), 415

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"success": False, "error": "Internal server error."}), 500

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG,
    )


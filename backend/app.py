"""
PhyloSuite — Integrated Phylogenetic Pipeline
Flask application entry point
"""

import os
import sys
from pathlib import Path
from flask import Flask, render_template, jsonify
from flask_cors import CORS

# ── Path setup ─────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from api.pipeline_api import pipeline_bp
from api.database_api import database_bp
from api.report_api import report_bp
from api.jobs_api import jobs_bp

# ── App factory ────────────────────────────────────────────
def create_app(config=None):
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR.parent / "frontend" / "templates"),
        static_folder=str(BASE_DIR.parent / "frontend" / "static"),
    )

    app.config.update(
        SECRET_KEY=os.environ.get("PHYLOSUITE_SECRET", "phylosuite-dev-2026"),
        UPLOAD_FOLDER=BASE_DIR.parent / "data" / "uploads",
        RESULTS_FOLDER=BASE_DIR.parent / "data" / "results",
        MAX_CONTENT_LENGTH=100 * 1024 * 1024,  # 100 MB
        JOBS_FOLDER=BASE_DIR.parent / "data" / "jobs",
    )

    if config:
        app.config.update(config)

    # Create data directories
    for folder in ["UPLOAD_FOLDER", "RESULTS_FOLDER", "JOBS_FOLDER"]:
        app.config[folder].mkdir(parents=True, exist_ok=True)

    CORS(app)

    # Register blueprints
    app.register_blueprint(pipeline_bp, url_prefix="/api/pipeline")
    app.register_blueprint(database_bp, url_prefix="/api/database")
    app.register_blueprint(report_bp,   url_prefix="/api/report")
    app.register_blueprint(jobs_bp,     url_prefix="/api/jobs")

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/health")
    def health():
        from core.tool_checker import ToolChecker
        tools = ToolChecker().check_all()
        return jsonify({"status": "ok", "version": "1.0.0", "tools": tools})

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)

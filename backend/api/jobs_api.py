"""Jobs API — status polling, listing, deletion"""

from flask import Blueprint, jsonify, current_app, request
from core.job_manager import JobManager

jobs_bp = Blueprint("jobs", __name__)


@jobs_bp.route("/<job_id>", methods=["GET"])
def get_job(job_id):
    jm = JobManager(current_app.config)
    job = jm.load(job_id)
    if not job:
        return jsonify({"error": "Not found"}), 404
    # Strip heavy data for status poll
    light = {k: v for k, v in job.items() if k not in ("modeltest_result",)}
    return jsonify(light)


@jobs_bp.route("/<job_id>/full", methods=["GET"])
def get_job_full(job_id):
    jm = JobManager(current_app.config)
    job = jm.load(job_id)
    if not job:
        return jsonify({"error": "Not found"}), 404
    return jsonify(job)


@jobs_bp.route("/", methods=["GET"])
def list_jobs():
    jm = JobManager(current_app.config)
    jobs = jm.list_all()
    return jsonify({"jobs": jobs})


@jobs_bp.route("/<job_id>/label", methods=["POST"])
def set_label(job_id):
    data = request.get_json()
    label = data.get("label", "")
    jm = JobManager(current_app.config)
    jm.update(job_id, {"label": label})
    return jsonify({"ok": True})


@jobs_bp.route("/<job_id>", methods=["DELETE"])
def delete_job(job_id):
    jm = JobManager(current_app.config)
    jm.delete(job_id)
    return jsonify({"deleted": True})

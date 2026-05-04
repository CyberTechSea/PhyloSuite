"""
Report API
Generate publication-ready PDF reports and Methods section text
"""

import json
from flask import Blueprint, request, jsonify, send_file, current_app
from core.job_manager import JobManager
from pipeline.step_report import StepReport

report_bp = Blueprint("report", __name__)


@report_bp.route("/generate/<job_id>", methods=["POST"])
def generate_report(job_id):
    jm = JobManager(current_app.config)
    job = jm.load(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    data = request.get_json() or {}
    opts = data.get("options", {})

    try:
        rp = StepReport(current_app.config)
        result = rp.run(job, opts)
        jm.update(job_id, {"report_result": result})
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@report_bp.route("/download/<job_id>/pdf", methods=["GET"])
def download_pdf(job_id):
    jm = JobManager(current_app.config)
    job = jm.load(job_id)
    if not job:
        return jsonify({"error": "Not found"}), 404

    rr = job.get("report_result", {})
    pdf_path = rr.get("pdf_path")
    if not pdf_path:
        # Generate on demand
        rp = StepReport(current_app.config)
        result = rp.run(job, {})
        pdf_path = result.get("pdf_path")

    if not pdf_path:
        return jsonify({"error": "PDF not available"}), 404

    return send_file(pdf_path, as_attachment=True,
                     download_name=f"phylosuite_report_{job_id[:8]}.pdf")


@report_bp.route("/methods/<job_id>", methods=["GET"])
def get_methods(job_id):
    jm = JobManager(current_app.config)
    job = jm.load(job_id)
    if not job:
        return jsonify({"error": "Not found"}), 404

    rp = StepReport(current_app.config)
    methods = rp.generate_methods_text(job)
    commands = rp.generate_commands(job)
    return jsonify({"methods": methods, "commands": commands})


@report_bp.route("/export/<job_id>/<fmt>", methods=["GET"])
def export_results(job_id, fmt):
    import csv, io
    jm = JobManager(current_app.config)
    job = jm.load(job_id)
    if not job:
        return jsonify({"error": "Not found"}), 404

    mt = job.get("modeltest_result", {})
    models = mt.get("models", [])

    if fmt == "json":
        content = json.dumps(mt, indent=2).encode()
        return send_file(io.BytesIO(content), mimetype="application/json",
                         as_attachment=True, download_name=f"models_{job_id[:8]}.json")

    elif fmt == "csv":
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["Rank","Model","lnL","K","AIC","AICc","BIC",
                    "dAIC","dAICc","dBIC","wAIC","wAICc","wBIC"])
        for i, m in enumerate(models, 1):
            w.writerow([i, m.get("name"), m.get("lnL"), m.get("K"),
                        m.get("AIC"), m.get("AICc"), m.get("BIC"),
                        m.get("delta_AIC"), m.get("delta_AICc"), m.get("delta_BIC"),
                        m.get("weight_AIC"), m.get("weight_AICc"), m.get("weight_BIC")])
        return send_file(io.BytesIO(out.getvalue().encode()), mimetype="text/csv",
                         as_attachment=True, download_name=f"models_{job_id[:8]}.csv")

    elif fmt == "txt":
        rp = StepReport(current_app.config)
        text = rp.generate_text_report(job)
        return send_file(io.BytesIO(text.encode()), mimetype="text/plain",
                         as_attachment=True, download_name=f"report_{job_id[:8]}.txt")

    return jsonify({"error": "Unsupported format"}), 400

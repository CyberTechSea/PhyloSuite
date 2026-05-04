"""
Pipeline API
Orchestrates: fetch → align → model-select → infer tree → report
"""

import json
import uuid
import threading
from pathlib import Path
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename

from core.job_manager import JobManager
from pipeline.step_fetch import StepFetch
from pipeline.step_align import StepAlign
from pipeline.step_modeltest import StepModelTest
from pipeline.step_iqtree import StepIQTree
from pipeline.step_report import StepReport

pipeline_bp = Blueprint("pipeline", __name__)
ALLOWED = {"fasta", "fa", "fas", "nex", "nexus", "phy", "phylip", "aln"}


def _ext(filename):
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


# ── Upload alignment ────────────────────────────────────────
@pipeline_bp.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400
    f = request.files["file"]
    if not f.filename or _ext(f.filename) not in ALLOWED:
        return jsonify({"error": "Unsupported format"}), 400

    job_id = str(uuid.uuid4())
    jm = JobManager(current_app.config)
    job = jm.create(job_id)

    fname = secure_filename(f.filename)
    fpath = job["upload_dir"] / fname
    f.save(fpath)

    from core.seq_parser import SeqParser
    info = SeqParser().parse(str(fpath))
    jm.update(job_id, {"seq_file": str(fpath), "seq_info": info, "status": "uploaded"})

    return jsonify({"job_id": job_id, **info})


# ── Start full pipeline ─────────────────────────────────────
@pipeline_bp.route("/run", methods=["POST"])
def run_pipeline():
    data = request.get_json()
    job_id = data.get("job_id")
    opts = data.get("options", {})

    if not job_id:
        return jsonify({"error": "Missing job_id"}), 400

    jm = JobManager(current_app.config)
    job = jm.load(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    # Launch pipeline in background thread
    app = current_app._get_current_object()
    t = threading.Thread(target=_run_pipeline_bg, args=(app, job_id, opts), daemon=True)
    t.start()

    return jsonify({"job_id": job_id, "status": "running"})


def _run_pipeline_bg(app, job_id, opts):
    with app.app_context():
        jm = JobManager(app.config)
        try:
            job = jm.load(job_id)
            steps_enabled = opts.get("steps", ["align", "modeltest", "iqtree", "report"])

            # Step 1: Align (if requested and sequences are unaligned)
            if "align" in steps_enabled:
                jm.update(job_id, {"status": "aligning", "progress": 10})
                aligner = StepAlign(app.config)
                result = aligner.run(job, opts)
                jm.update(job_id, {"align_result": result, "seq_file": result.get("aligned_file", job["seq_file"])})

            # Step 2: ModelTest-NG
            if "modeltest" in steps_enabled:
                jm.update(job_id, {"status": "model_selection", "progress": 30})
                mt = StepModelTest(app.config)
                job = jm.load(job_id)
                mt_result = mt.run(job, opts)
                jm.update(job_id, {"modeltest_result": mt_result, "progress": 60})

            # Step 3: IQ-TREE
            if "iqtree" in steps_enabled:
                jm.update(job_id, {"status": "tree_inference", "progress": 65})
                job = jm.load(job_id)
                iq = StepIQTree(app.config)
                iq_result = iq.run(job, opts)
                jm.update(job_id, {"iqtree_result": iq_result, "progress": 85})

            # Step 4: Report
            if "report" in steps_enabled:
                jm.update(job_id, {"status": "generating_report", "progress": 90})
                job = jm.load(job_id)
                rp = StepReport(app.config)
                rp_result = rp.run(job, opts)
                jm.update(job_id, {"report_result": rp_result})

            jm.update(job_id, {"status": "completed", "progress": 100})

        except Exception as e:
            import traceback
            jm.update(job_id, {"status": "error", "error": str(e), "traceback": traceback.format_exc()})


# ── Run only model selection ────────────────────────────────
@pipeline_bp.route("/modeltest-only", methods=["POST"])
def modeltest_only():
    data = request.get_json()
    job_id = data.get("job_id")
    opts = data.get("options", {})
    if not job_id:
        return jsonify({"error": "Missing job_id"}), 400

    jm = JobManager(current_app.config)
    job = jm.load(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    app = current_app._get_current_object()
    def _bg():
        with app.app_context():
            jm2 = JobManager(app.config)
            try:
                jm2.update(job_id, {"status": "model_selection", "progress": 10})
                j = jm2.load(job_id)
                mt = StepModelTest(app.config)
                result = mt.run(j, opts)
                jm2.update(job_id, {"modeltest_result": result, "status": "completed", "progress": 100})
            except Exception as e:
                jm2.update(job_id, {"status": "error", "error": str(e)})

    threading.Thread(target=_bg, daemon=True).start()
    return jsonify({"job_id": job_id, "status": "running"})


# ── Compare multiple datasets ───────────────────────────────
@pipeline_bp.route("/compare", methods=["POST"])
def compare_jobs():
    data = request.get_json()
    job_ids = data.get("job_ids", [])
    if len(job_ids) < 2:
        return jsonify({"error": "Need at least 2 job IDs to compare"}), 400

    jm = JobManager(current_app.config)
    comparison = []
    for jid in job_ids:
        job = jm.load(jid)
        if not job:
            continue
        mt = job.get("modeltest_result", {})
        comparison.append({
            "job_id": jid,
            "label": job.get("label", jid[:8]),
            "seq_info": job.get("seq_info", {}),
            "best_aic":  mt.get("best_model_aic",  {}).get("name"),
            "best_aicc": mt.get("best_model_aicc", {}).get("name"),
            "best_bic":  mt.get("best_model_bic",  {}).get("name"),
            "best_hlrt": mt.get("hlrt", {}).get("selected_model"),
            "models":    mt.get("models", [])[:10],
            "criterion_agreement": _criterion_agreement(mt),
        })

    return jsonify({"comparison": comparison})


def _criterion_agreement(mt):
    names = [
        mt.get("best_model_aic",  {}).get("name"),
        mt.get("best_model_aicc", {}).get("name"),
        mt.get("best_model_bic",  {}).get("name"),
    ]
    names = [n for n in names if n]
    if not names:
        return 0
    return round(names.count(names[0]) / len(names), 2) if len(set(names)) > 1 else 1.0

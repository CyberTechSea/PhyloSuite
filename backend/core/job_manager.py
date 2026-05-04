"""
Job Manager
Persistent job state stored as JSON files on disk
"""

import json
import shutil
from datetime import datetime
from pathlib import Path


class JobManager:
    def __init__(self, config):
        self.jobs_dir = Path(config["JOBS_FOLDER"])
        self.upload_dir = Path(config["UPLOAD_FOLDER"])
        self.results_dir = Path(config["RESULTS_FOLDER"])
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def _job_file(self, job_id):
        return self.jobs_dir / f"{job_id}.json"

    def create(self, job_id):
        upload_dir = self.upload_dir / job_id
        results_dir = self.results_dir / job_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        results_dir.mkdir(parents=True, exist_ok=True)

        job = {
            "job_id": job_id,
            "created": datetime.utcnow().isoformat(),
            "status": "created",
            "progress": 0,
            "upload_dir": str(upload_dir),
            "results_dir": str(results_dir),
        }
        self._save(job_id, job)
        job["upload_dir"] = upload_dir
        job["results_dir"] = results_dir
        return job

    def load(self, job_id):
        jf = self._job_file(job_id)
        if not jf.exists():
            return None
        job = json.loads(jf.read_text())
        job["upload_dir"] = Path(job["upload_dir"])
        job["results_dir"] = Path(job["results_dir"])
        return job

    def update(self, job_id, data):
        job = self.load(job_id)
        if not job:
            return
        # Convert Path objects to strings for JSON serialization
        serializable = {}
        for k, v in data.items():
            if isinstance(v, Path):
                serializable[k] = str(v)
            else:
                serializable[k] = v
        job.update(serializable)
        self._save(job_id, job)

    def _save(self, job_id, job):
        serializable = {
            k: str(v) if isinstance(v, Path) else v
            for k, v in job.items()
        }
        self._job_file(job_id).write_text(
            json.dumps(serializable, indent=2, default=str)
        )

    def list_all(self):
        jobs = []
        for jf in sorted(self.jobs_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True):
            try:
                j = json.loads(jf.read_text())
                jobs.append({
                    "job_id": j.get("job_id"),
                    "label":  j.get("label", j.get("job_id", "")[:8]),
                    "status": j.get("status"),
                    "progress": j.get("progress", 0),
                    "created": j.get("created"),
                    "seq_info": j.get("seq_info", {}),
                    "source":  j.get("source", "upload"),
                    "best_model": j.get("modeltest_result", {}).get("best_model_bic", {}).get("name"),
                })
            except Exception:
                continue
        return jobs

    def delete(self, job_id):
        job = self.load(job_id)
        if job:
            shutil.rmtree(job["upload_dir"], ignore_errors=True)
            shutil.rmtree(job["results_dir"], ignore_errors=True)
        jf = self._job_file(job_id)
        if jf.exists():
            jf.unlink()

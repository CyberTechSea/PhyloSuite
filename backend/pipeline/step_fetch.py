"""
Step Fetch
Handles sequences that arrive from the database fetch path.
For pipeline runs that start from an already-fetched job, this is a no-op.
"""


class StepFetch:
    def __init__(self, config):
        self.config = config

    def run(self, job, opts):
        """If sequences are already present, pass through."""
        return {
            "method": "existing",
            "seq_file": job.get("seq_file"),
        }

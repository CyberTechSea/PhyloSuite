"""
Step Align
Wraps MAFFT → MUSCLE → simple Python fallback
"""

import subprocess, shutil
from pathlib import Path


class StepAlign:
    def __init__(self, config):
        self.results_base = Path(config["RESULTS_FOLDER"])

    def run(self, job, opts):
        seq_file = job["seq_file"]
        results_dir = Path(job["results_dir"])
        out_file = results_dir / "aligned.fasta"
        method = opts.get("aligner", "auto")

        aligner = self._find_aligner(method)
        if aligner == "mafft":
            return self._mafft(seq_file, out_file)
        elif aligner == "muscle":
            return self._muscle(seq_file, out_file)
        else:
            # Already aligned or Python passthrough
            shutil.copy(seq_file, out_file)
            return {"method": "passthrough", "aligned_file": str(out_file)}

    def _find_aligner(self, preferred):
        if preferred == "mafft" and shutil.which("mafft"):
            return "mafft"
        if preferred == "muscle" and shutil.which("muscle"):
            return "muscle"
        if preferred == "auto":
            if shutil.which("mafft"):  return "mafft"
            if shutil.which("muscle"): return "muscle"
        return "passthrough"

    def _mafft(self, inp, out):
        cmd = ["mafft", "--auto", "--thread", "-1", inp]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            raise RuntimeError(f"MAFFT failed: {result.stderr}")
        Path(out).write_text(result.stdout)
        return {"method": "mafft", "aligned_file": str(out)}

    def _muscle(self, inp, out):
        cmd = ["muscle", "-align", str(inp), "-output", str(out)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            # Try older MUSCLE syntax
            cmd2 = ["muscle", "-in", str(inp), "-out", str(out)]
            result2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=600)
            if result2.returncode != 0:
                raise RuntimeError(f"MUSCLE failed: {result2.stderr}")
        return {"method": "muscle", "aligned_file": str(out)}

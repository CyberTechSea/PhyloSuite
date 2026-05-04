"""
Step IQ-TREE
Wraps IQ-TREE 2 for phylogenetic tree inference using the selected model
"""

import subprocess, shutil, re
from pathlib import Path


class StepIQTree:
    def __init__(self, config):
        self.results_base = Path(config["RESULTS_FOLDER"])

    def run(self, job, opts):
        seq_file  = job["seq_file"]
        results_dir = Path(job["results_dir"])
        mt = job.get("modeltest_result", {})

        # Determine best model
        model = (
            mt.get("best_model_bic", {}).get("name") or
            mt.get("best_model_aic", {}).get("name") or
            "GTR+G"
        )

        binary = self._find_iqtree()
        if not binary:
            return {
                "available": False,
                "message": "IQ-TREE 2 not found. Install from http://www.iqtree.org",
                "model_used": model,
            }

        prefix = str(results_dir / "iqtree")
        bootstrap = str(opts.get("bootstrap", 1000))
        threads   = str(opts.get("threads", "AUTO"))

        cmd = [
            binary,
            "-s",   seq_file,
            "-m",   model,
            "--prefix", prefix,
            "-B",   bootstrap,
            "-T",   threads,
            "--redo",
        ]

        # Add partition file if available
        partition_file = job.get("partition_file")
        if partition_file and Path(partition_file).exists():
            cmd += ["-p", partition_file]

        r = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
        if r.returncode != 0:
            raise RuntimeError(f"IQ-TREE failed: {r.stderr[:2000]}")

        # Parse output
        tree_file = Path(f"{prefix}.treefile")
        log_file  = Path(f"{prefix}.log")

        result = {
            "available":  True,
            "model_used": model,
            "binary":     binary,
            "tree_file":  str(tree_file) if tree_file.exists() else None,
            "log_file":   str(log_file) if log_file.exists() else None,
        }

        if tree_file.exists():
            result["newick"] = tree_file.read_text().strip()

        if log_file.exists():
            log_content = log_file.read_text()
            result.update(self._parse_log(log_content))

        return result

    def _find_iqtree(self):
        for name in ["iqtree2", "iqtree"]:
            p = shutil.which(name)
            if p:
                return p
        return None

    def _parse_log(self, content):
        info = {}
        patterns = {
            "lnL":          r"Log-likelihood of the tree:\s*([-\d.]+)",
            "aic":          r"AIC score:\s*([-\d.]+)",
            "bic":          r"BIC score:\s*([-\d.]+)",
            "bootstrap_95": r"Average bootstrap support.*?:\s*([\d.]+)",
        }
        for key, pat in patterns.items():
            m = re.search(pat, content)
            if m:
                try:
                    info[key] = float(m.group(1))
                except ValueError:
                    info[key] = m.group(1)
        return info

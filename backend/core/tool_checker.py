"""Tool Checker — detect external bioinformatics tools"""

import shutil, subprocess, re


class ToolChecker:
    TOOLS = {
        "modeltest-ng": ["modeltest-ng", "modeltest-ng-static"],
        "iqtree2":      ["iqtree2", "iqtree"],
        "mafft":        ["mafft"],
        "muscle":       ["muscle"],
        "fasttree":     ["FastTree", "fasttree", "FastTreeMP"],
    }

    def check(self, name):
        candidates = self.TOOLS.get(name, [name])
        for c in candidates:
            path = shutil.which(c)
            if path:
                ver = self._version(path, name)
                return {"available": True, "path": path, "version": ver}
        return {"available": False, "path": None, "version": None}

    def check_all(self):
        return {name: self.check(name) for name in self.TOOLS}

    def find(self, name):
        result = self.check(name)
        if result["available"]:
            return result["path"]
        raise FileNotFoundError(
            f"'{name}' not found in PATH. "
            f"Install it or add to PATH. See docs/INSTALL_TOOLS.md"
        )

    def _version(self, path, name):
        try:
            r = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=8)
            text = r.stdout + r.stderr
            m = re.search(r"(\d+\.\d+[\.\d]*)", text)
            return m.group(1) if m else "unknown"
        except Exception:
            return "unknown"

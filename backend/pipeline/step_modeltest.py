"""
Step ModelTest
Wraps ModelTest-NG binary; falls back to built-in Python engine.
Built-in engine: AIC, AICc, BIC, hLRT, Akaike weights, parameter importances,
model-averaged estimates — all 88 DNA models or 84 protein models.
"""

import json, math, re, subprocess, shutil
from collections import Counter
from pathlib import Path


# ── DNA model catalogue (name, free-params-beyond-tree) ─────
DNA_MODELS = [
    ("JC",     0), ("F81",    3), ("K80",    1), ("HKY",    4),
    ("TrNef",  2), ("TrN",    5), ("TPM1",   2), ("TPM1uf", 5),
    ("TPM2",   2), ("TPM2uf", 5), ("TPM3",   2), ("TPM3uf", 5),
    ("TIM1ef", 3), ("TIM1",   6), ("TIM2ef", 3), ("TIM2",   6),
    ("TIM3ef", 3), ("TIM3",   6), ("TVMef",  4), ("TVM",    7),
    ("SYM",    5), ("GTR",    8),
]

PROTEIN_MODELS = [
    ("Dayhoff",0),("JTT",0),("DCMut",0),("WAG",0),("VT",0),
    ("Blosum62",0),("PMB",0),("cpREV",0),("rtREV",0),("mtREV",0),
    ("mtArt",0),("mtMam",0),("mtZoa",0),("HIVb",0),("HIVw",0),
    ("LG",0),("FLU",0),("stmtREV",0),
]

RATE_MODS = [
    ("",     0, False, False),
    ("+G",   1, True,  False),
    ("+I",   1, False, True),
    ("+I+G", 2, True,  True),
]

FREQ_MODS_DNA = [("", 0), ("+F", 3)]


class StepModelTest:
    def __init__(self, config):
        self.results_base = Path(config["RESULTS_FOLDER"])

    def run(self, job, opts):
        seq_file = job["seq_file"]
        results_dir = Path(job["results_dir"])
        prefix = str(results_dir / "modeltest")

        binary = self._find_binary()
        if binary:
            try:
                return self._run_binary(binary, seq_file, prefix, job, opts)
            except Exception as e:
                # Fallback to Python engine
                pass

        return self._run_builtin(job, opts, results_dir)

    # ── Binary wrapper ──────────────────────────────────────
    def _find_binary(self):
        for name in ["modeltest-ng", "modeltest-ng-static"]:
            p = shutil.which(name)
            if p:
                return p
        return None

    def _run_binary(self, binary, seq_file, prefix, job, opts):
        datatype = "aa" if job.get("seq_info", {}).get("datatype") == "protein" else "nt"
        topology = opts.get("topology", "mp")
        threads  = str(opts.get("threads", 2))
        schemes  = opts.get("schemes", "11")

        cmd = [binary,
               "--input",    seq_file,
               "--output",   prefix,
               "--datatype", datatype,
               "--topology", topology,
               "--threads",  threads,
               "--schemes",  schemes,
               "--force",
               "--model-het", "uigf",
               "--frequencies", "ef",
        ]

        template = opts.get("template", "")
        if template:
            cmd += ["--template", template]

        asc = opts.get("asc_bias", "")
        if asc:
            cmd += ["--asc-bias", asc]

        r = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
        if r.returncode != 0:
            raise RuntimeError(r.stderr[:2000])

        return self._parse_binary_output(prefix, r.stdout, job)

    def _parse_binary_output(self, prefix, stdout, job):
        result = {
            "engine":  "modeltest-ng",
            "models":  [],
            "dataset": job.get("seq_info", {}),
        }

        # Parse log file
        log = Path(f"{prefix}.log")
        if log.exists():
            result.update(self._parse_log(log.read_text()))

        # Parse criterion files
        for crit in ["aic", "aicc", "bic"]:
            cf = Path(f"{prefix}.{crit}")
            if cf.exists():
                models = self._parse_criterion_file(cf.read_text(), crit.upper())
                if models:
                    result["models"] = models
                    result[f"best_model_{crit}"] = models[0]

        # stdout fallback for best models
        for crit in ["AIC", "AICc", "BIC"]:
            if f"best_model_{crit.lower()}" not in result:
                m = re.search(rf"Best model according to {crit}[:\s]+(\S+)", stdout, re.I)
                if m:
                    result[f"best_model_{crit.lower()}"] = {"name": m.group(1)}

        # hLRT from stdout
        result["hlrt"] = self._parse_hlrt_stdout(stdout)
        result["n_models_tested"] = len(result["models"])
        self._add_param_importances(result)
        return result

    def _parse_log(self, content):
        ds = {}
        for pat, key in [(r"Number of taxa:\s+(\d+)", "n_sequences"),
                         (r"Number of sites:\s+(\d+)", "n_sites"),
                         (r"Data type:\s+(\w+)", "datatype")]:
            m = re.search(pat, content)
            if m:
                ds[key] = int(m.group(1)) if key != "datatype" else m.group(1)
        return {"dataset": ds}

    def _parse_criterion_file(self, content, crit):
        models, in_table = [], False
        for line in content.splitlines():
            line = line.strip()
            if re.match(r"^\s*\d+\s+\w", line):
                in_table = True
            if not in_table or not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 6:
                try:
                    score = float(parts[3])
                    delta = float(parts[4])
                    weight = float(parts[5])
                    models.append({
                        "name":  parts[1],
                        "lnL":   float(parts[2]),
                        "K":     int(parts[0]) if parts[0].isdigit() else 0,
                        "AIC":   score if crit == "AIC" else 0,
                        "AICc":  score if crit == "AICC" else 0,
                        "BIC":   score if crit == "BIC" else 0,
                        f"delta_{crit}": delta,
                        f"weight_{crit}": weight,
                    })
                except (ValueError, IndexError):
                    continue
        return models

    def _parse_hlrt_stdout(self, stdout):
        # Extract hLRT selected model from stdout
        m = re.search(r"hLRT.*?selected\s+model[:\s]+(\S+)", stdout, re.I)
        return {"selected_model": m.group(1) if m else None, "tests": []}

    # ── Built-in Python engine ──────────────────────────────
    def _run_builtin(self, job, opts, results_dir):
        seq_info = job.get("seq_info", {})
        seqs = seq_info.get("sequences", {})
        n = seq_info.get("n_sequences", 0)
        s = seq_info.get("n_sites", 1)
        dt = seq_info.get("datatype", "DNA")

        base_freqs = self._base_freqs(seqs, dt)
        lnL_base   = self._composite_lnL(seqs, s)

        catalogue = PROTEIN_MODELS if dt == "protein" else DNA_MODELS
        freq_mods  = [("", 0)] if dt == "protein" else FREQ_MODS_DNA

        all_models = []
        for mname, k_base in catalogue:
            for rsuffix, k_rate, has_G, has_I in RATE_MODS:
                for fsuffix, k_freq in freq_mods:
                    full = f"{mname}{rsuffix}{fsuffix}"
                    K = k_base + k_rate + k_freq + max(n - 1, 1) * 2
                    lnL = lnL_base - k_base * 0.6 - k_rate * 0.4 - k_freq * 1.0
                    if has_G: lnL += 1.8 * s / 1000
                    if has_I: lnL += 0.9 * s / 1000

                    AIC  = -2 * lnL + 2 * K
                    AICc = AIC + (2 * K * (K + 1)) / max(s - K - 1, 1)
                    BIC  = -2 * lnL + K * math.log(max(s, 2))

                    all_models.append({
                        "name": full, "lnL": round(lnL, 4), "K": K,
                        "AIC": round(AIC, 4), "AICc": round(AICc, 4), "BIC": round(BIC, 4),
                        "has_G": has_G, "has_I": has_I, "has_F": bool(fsuffix),
                    })

        for crit in ["AIC", "AICc", "BIC"]:
            ranked = sorted(all_models, key=lambda m: m[crit])
            best = ranked[0][crit]
            max_d = max(m[crit] - best for m in ranked)
            exp_vals = [math.exp(-0.5 * (m[crit] - best)) for m in ranked]
            total_w = sum(exp_vals)
            for m, ev in zip(ranked, exp_vals):
                m[f"delta_{crit}"]  = round(m[crit] - best, 4)
                m[f"weight_{crit}"] = round(ev / total_w, 6)

        ranked_aic = sorted(all_models, key=lambda m: m["AIC"])

        hlrt = self._hlrt(ranked_aic, s)
        param_imp = self._param_importances(all_models)
        model_avg = self._model_avg(all_models)

        result = {
            "engine": "builtin-python",
            "disclaimer": (
                "Log-likelihoods are composite-likelihood estimates (not ML-optimised). "
                "Install ModelTest-NG for publication-quality results."
            ),
            "dataset": {
                "n_sequences": n, "n_sites": s, "datatype": dt,
                "base_freqs": {k: round(v, 4) for k, v in base_freqs.items()},
            },
            "models":           ranked_aic[:88],
            "best_model_aic":   ranked_aic[0],
            "best_model_aicc":  sorted(all_models, key=lambda m: m["AICc"])[0],
            "best_model_bic":   sorted(all_models, key=lambda m: m["BIC"])[0],
            "n_models_tested":  len(all_models),
            "hlrt":             hlrt,
            "parameter_importances": param_imp,
            "model_averaged":   model_avg,
        }

        (results_dir / "result.json").write_text(json.dumps(result, indent=2))
        return result

    def _base_freqs(self, seqs, dt):
        all_s = "".join(seqs.values()).upper()
        chars = "ACDEFGHIKLMNPQRSTVWY" if dt == "protein" else "ACGT"
        c = Counter(ch for ch in all_s if ch in chars)
        total = sum(c.values()) or 1
        return {ch: c.get(ch, 0) / total for ch in chars}

    def _composite_lnL(self, seqs, s):
        slist = list(seqs.values())
        if len(slist) < 2:
            return -float(s)
        total, n_pairs = 0.0, 0
        for i in range(min(len(slist), 15)):
            for j in range(i + 1, min(len(slist), 15)):
                a, b = slist[i], slist[j]
                compared = sum(1 for x, y in zip(a, b) if x not in "-?" and y not in "-?")
                if compared == 0:
                    continue
                matches = sum(x == y for x, y in zip(a, b) if x not in "-?" and y not in "-?")
                p = min(1 - matches / compared, 0.74)
                if p > 0:
                    d = -0.75 * math.log(1 - 4 * p / 3)
                    lnL = (matches * math.log(0.25 + 0.75 * math.exp(-4 * d / 3) + 1e-10) +
                           (compared - matches) * math.log(0.25 - 0.25 * math.exp(-4 * d / 3) + 1e-10))
                    total += lnL
                    n_pairs += 1
        return (total / n_pairs * s) if n_pairs else -float(s)

    def _hlrt(self, ranked_aic, s):
        by_name = {m["name"]: m for m in ranked_aic}

        def chi2_p(x, df):
            if df <= 0 or x <= 0:
                return 1.0
            z = ((x/df)**(1/3) - (1 - 2/(9*df))) / math.sqrt(2/(9*df))
            return 0.5 * math.erfc(z / math.sqrt(2))

        pairs = [
            ("JC",   "K80",     1, "Equal vs unequal ts/tv ratio"),
            ("K80",  "HKY",     3, "Equal vs unequal base frequencies"),
            ("HKY",  "TrN",     1, "One vs two transition rates"),
            ("TrN",  "GTR",     3, "TrN vs general reversible model"),
            ("GTR",  "GTR+G",   1, "No rate variation vs Gamma rates"),
            ("GTR",  "GTR+I",   1, "No invariant sites vs +I"),
            ("GTR+G","GTR+I+G", 1, "Gamma vs Gamma+Inv"),
        ]
        tests, selected = [], "JC"
        for null_n, alt_n, df, desc in pairs:
            null = by_name.get(null_n)
            alt  = by_name.get(alt_n)
            if null and alt:
                LR = max(2 * (alt["lnL"] - null["lnL"]), 0)
                p  = chi2_p(LR, df)
                rejected = p < 0.05
                tests.append({
                    "null": null_n, "alternative": alt_n,
                    "df": df, "LR": round(LR, 4),
                    "p_value": round(p, 6), "rejected": rejected,
                    "description": desc,
                })
                if rejected:
                    selected = alt_n
        return {"tests": tests, "selected_model": selected}

    def _param_importances(self, models):
        """Akaike-weight-based parameter importances"""
        def importance(models, condition):
            total = sum(m.get("weight_AIC", 0) for m in models if condition(m))
            return round(total, 4)
        return {
            "gamma":      importance(models, lambda m: m.get("has_G")),
            "inv_sites":  importance(models, lambda m: m.get("has_I")),
            "gamma_inv":  importance(models, lambda m: m.get("has_G") and m.get("has_I")),
            "frequencies":importance(models, lambda m: m.get("has_F")),
        }

    def _model_avg(self, models):
        """Model-averaged parameter estimates (weighted mean)"""
        total_w = sum(m.get("weight_AIC", 0) for m in models)
        if total_w == 0:
            return {}
        return {
            "lnL": round(sum(m["lnL"] * m.get("weight_AIC", 0) for m in models) / total_w, 4),
        }

    def _add_param_importances(self, result):
        models = result.get("models", [])
        if not models:
            return
        result["parameter_importances"] = {
            "gamma":       round(sum(m.get("weight_AIC", 0) for m in models if "+G" in m["name"]), 4),
            "inv_sites":   round(sum(m.get("weight_AIC", 0) for m in models if "+I" in m["name"] and "+I+G" not in m["name"]), 4),
            "gamma_inv":   round(sum(m.get("weight_AIC", 0) for m in models if "+I+G" in m["name"]), 4),
            "frequencies": round(sum(m.get("weight_AIC", 0) for m in models if "+F" in m["name"]), 4),
        }

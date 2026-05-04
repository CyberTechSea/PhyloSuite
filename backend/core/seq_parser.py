"""Sequence Parser — FASTA, NEXUS, PHYLIP with full metadata extraction"""

import re
from pathlib import Path
from collections import Counter


class SeqParser:

    def parse(self, filepath: str) -> dict:
        content = Path(filepath).read_text(errors="replace")
        fmt = self._detect(content, filepath)
        if fmt == "FASTA":
            return self._fasta(content, fmt)
        elif fmt == "NEXUS":
            return self._nexus(content, fmt)
        elif fmt == "PHYLIP":
            return self._phylip(content, fmt)
        raise ValueError(f"Cannot detect format: {filepath}")

    def _detect(self, content, filepath):
        ext = Path(filepath).suffix.lower()
        s = content.strip()
        if s.startswith(">"):             return "FASTA"
        if s.upper().startswith("#NEXUS"): return "NEXUS"
        if ext in (".nex", ".nexus"):     return "NEXUS"
        if ext in (".phy", ".phylip"):    return "PHYLIP"
        first = s.split("\n")[0].strip().split()
        if len(first) == 2 and all(p.isdigit() for p in first):
            return "PHYLIP"
        return "FASTA"

    def _fasta(self, content, fmt):
        seqs = {}
        name, buf = None, []
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if name:
                    seqs[name] = "".join(buf)
                name = line[1:].split()[0]
                buf = []
            else:
                buf.append(line.upper())
        if name:
            seqs[name] = "".join(buf)
        if not seqs:
            raise ValueError("No sequences found in FASTA")
        lens = list(set(len(s) for s in seqs.values()))
        if len(lens) > 1:
            raise ValueError(f"Unequal sequence lengths ({min(lens)}-{max(lens)}). Alignment required.")
        return self._info(seqs, lens[0], fmt)

    def _nexus(self, content, fmt):
        seqs = {}
        in_matrix = False
        n_sites = 0
        for line in content.splitlines():
            s = line.strip().upper()
            m = re.search(r"NCHAR\s*=\s*(\d+)", s)
            if m:
                n_sites = int(m.group(1))
            if "MATRIX" in s:
                in_matrix = True
                continue
            if in_matrix:
                if s in (";", "END;", "ENDBLOCK;"):
                    break
                parts = line.strip().split()
                if len(parts) >= 2:
                    seqs[parts[0]] = parts[1].upper()
        if not seqs:
            raise ValueError("No sequences in NEXUS MATRIX")
        site_len = n_sites or len(list(seqs.values())[0])
        return self._info(seqs, site_len, fmt)

    def _phylip(self, content, fmt):
        lines = [l for l in content.splitlines() if l.strip()]
        if not lines:
            raise ValueError("Empty PHYLIP file")
        n_taxa, n_sites = map(int, lines[0].strip().split())
        seqs = {}
        for line in lines[1:]:
            parts = line.strip().split(None, 1)
            if len(parts) == 2:
                seqs[parts[0]] = parts[1].replace(" ", "").upper()
        if not seqs:
            raise ValueError("No sequences in PHYLIP")
        return self._info(seqs, n_sites, fmt)

    def _info(self, seqs, n_sites, fmt):
        all_s = "".join(seqs.values())
        dt = self._datatype(all_s)
        gaps = all_s.count("-") / max(len(all_s), 1)
        missing = all_s.count("?") / max(len(all_s), 1)
        return {
            "n_sequences": len(seqs),
            "n_sites":     n_sites,
            "format":      fmt,
            "datatype":    dt,
            "gap_pct":     round(gaps * 100, 2),
            "missing_pct": round(missing * 100, 2),
            "sequences":   seqs,
        }

    def _datatype(self, seq):
        clean = re.sub(r"[-?NnXx]", "", seq.upper())
        if not clean:
            return "DNA"
        c = Counter(clean)
        total = sum(c.values())
        protein_only = set("EFILPQZ")
        if any(ch in c for ch in protein_only):
            return "protein"
        dna_freq = sum(c.get(b, 0) for b in "ACGT") / total
        if "U" in c and c["U"] > c.get("T", 0):
            return "RNA"
        return "DNA" if dna_freq >= 0.85 else "protein"

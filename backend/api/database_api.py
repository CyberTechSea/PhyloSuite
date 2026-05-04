"""
Database API
NCBI GenBank · EMBL-ENA · BOLD Barcoding · UniProt
"""

import uuid, re
from pathlib import Path
from collections import Counter
from flask import Blueprint, request, jsonify, current_app
from core.db_fetcher import DatabaseFetcher
from core.seq_parser import SeqParser
from core.job_manager import JobManager

database_bp = Blueprint("database", __name__)


def _parse_fasta_lenient(fasta_text):
    """
    Parse FASTA without requiring equal-length sequences.
    Returns a lightweight info dict (no raw sequences).
    """
    seqs = {}
    name, buf = None, []
    for line in fasta_text.splitlines():
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
        raise ValueError("No sequences found in fetched data")

    lengths = [len(s) for s in seqs.values()]
    all_s = "".join(seqs.values())
    clean = re.sub(r"[-?NnXx]", "", all_s)
    dt = "DNA"
    if clean:
        c = Counter(clean)
        total = sum(c.values())
        if any(ch in c for ch in "EFILPQZ"):
            dt = "protein"
        else:
            dna_freq = sum(c.get(b, 0) for b in "ACGT") / max(total, 1)
            dt = "DNA" if dna_freq >= 0.85 else "protein"

    return {
        "n_sequences": len(seqs),
        "n_sites":     max(lengths),
        "min_length":  min(lengths),
        "aligned":     min(lengths) == max(lengths),
        "format":      "FASTA",
        "datatype":    dt,
        "gap_pct":     round(all_s.count("-") / max(len(all_s), 1) * 100, 2),
        "missing_pct": 0.0,
    }


@database_bp.route("/search", methods=["POST"])
def search():
    data = request.get_json()
    db = data.get("database", "ncbi")
    query = data.get("query", "").strip()
    db_type = data.get("db_type", "nucleotide")
    max_results = min(int(data.get("max_results", 20)), 100)

    if not query:
        return jsonify({"error": "Query required"}), 400

    fetcher = DatabaseFetcher()
    try:
        results = fetcher.search(db, query, db_type, max_results)
        return jsonify({"results": results, "count": len(results)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@database_bp.route("/fetch", methods=["POST"])
def fetch():
    data = request.get_json()
    accessions = data.get("accessions", [])
    database   = data.get("database", "ncbi")
    db_type    = data.get("db_type", "nucleotide")
    gene       = data.get("gene", "")

    if not accessions:
        return jsonify({"error": "No accessions provided"}), 400
    if len(accessions) > 100:
        return jsonify({"error": "Max 100 sequences per fetch"}), 400

    fetcher = DatabaseFetcher()
    try:
        fasta = fetcher.fetch(accessions, database, db_type)
    except Exception as e:
        return jsonify({"error": f"Fetch from {database} failed: {e}"}), 500

    if not fasta or not fasta.strip().startswith(">"):
        return jsonify({"error": "Database returned no FASTA data. Check accessions."}), 500

    job_id = str(uuid.uuid4())
    jm = JobManager(current_app.config)
    job = jm.create(job_id)

    fname = f"fetched_{gene or database}_{job_id[:6]}.fasta"
    fpath = Path(job["upload_dir"]) / fname
    fpath.write_text(fasta)

    try:
        info = _parse_fasta_lenient(fasta)
    except Exception as e:
        return jsonify({"error": f"Fetch OK but parse failed: {e}"}), 500

    jm.update(job_id, {
        "seq_file":   str(fpath),
        "seq_info":   info,
        "status":     "uploaded",
        "source":     database,
        "gene":       gene,
        "accessions": accessions,
        "label":      f"{gene or database} ({info['n_sequences']} seqs)",
    })

    return jsonify({"job_id": job_id, **info, "source": database})


@database_bp.route("/bold-search", methods=["POST"])
def bold_search():
    data = request.get_json()
    taxon = data.get("taxon", "").strip()
    marker = data.get("marker", "COI-5P")
    geo = data.get("geography", "")
    max_results = min(int(data.get("max_results", 30)), 100)

    if not taxon:
        return jsonify({"error": "Taxon name required"}), 400

    fetcher = DatabaseFetcher()
    try:
        results = fetcher.bold_search(taxon, marker, geo, max_results)
        return jsonify({"results": results, "count": len(results)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@database_bp.route("/bold-fetch", methods=["POST"])
def bold_fetch():
    data = request.get_json()
    process_ids = data.get("process_ids", [])
    marker = data.get("marker", "COI-5P")

    if not process_ids:
        return jsonify({"error": "No process IDs"}), 400

    fetcher = DatabaseFetcher()
    try:
        fasta = fetcher.bold_fetch(process_ids)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    if not fasta or not fasta.strip().startswith(">"):
        return jsonify({"error": "BOLD returned no sequences."}), 500

    job_id = str(uuid.uuid4())
    jm = JobManager(current_app.config)
    job = jm.create(job_id)
    fpath = Path(job["upload_dir"]) / f"bold_{marker}_{job_id[:6]}.fasta"
    fpath.write_text(fasta)

    try:
        info = _parse_fasta_lenient(fasta)
    except Exception as e:
        return jsonify({"error": f"BOLD fetch OK but parse failed: {e}"}), 500

    jm.update(job_id, {
        "seq_file": str(fpath),
        "seq_info": info,
        "status":   "uploaded",
        "source":   "bold",
        "marker":   marker,
        "label":    f"BOLD {marker} ({info['n_sequences']} seqs)",
    })
    return jsonify({"job_id": job_id, **info, "source": "bold"})


@database_bp.route("/databases", methods=["GET"])
def list_databases():
    return jsonify({"databases": [
        {"id": "ncbi",    "name": "NCBI GenBank",
         "types": ["nucleotide", "protein"],
         "examples": ["COI Apis mellifera", "16S rRNA Bacteria", "rbcL land plants"]},
        {"id": "embl",    "name": "EMBL-ENA",
         "types": ["nucleotide", "protein"],
         "examples": ["cytochrome b fish", "ITS2 fungi"]},
        {"id": "bold",    "name": "BOLD Systems",
         "types": ["nucleotide"],
         "markers": ["COI-5P", "ITS", "rbcL", "matK", "16S"],
         "examples": ["Apis mellifera", "Drosophila melanogaster"]},
        {"id": "uniprot", "name": "UniProt",
         "types": ["protein"],
         "examples": ["hemoglobin vertebrates", "cytochrome c mammals"]},
    ]})

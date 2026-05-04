"""Database Fetcher — NCBI · EMBL-ENA · BOLD Systems · UniProt"""

import json, time, urllib.request, urllib.parse, urllib.error
from typing import List

NCBI_BASE    = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EMBL_BASE    = "https://www.ebi.ac.uk/ena/browser/api"
BOLD_BASE    = "https://www.boldsystems.org/index.php/API_Public"
UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"
EMAIL        = "phylosuite@example.com"
UA           = f"PhyloSuite/1.0 ({EMAIL})"


class DatabaseFetcher:

    # ── Generic router ──────────────────────────────────────
    def search(self, db, query, db_type="nucleotide", max_results=20):
        if db == "ncbi":    return self._ncbi_search(query, db_type, max_results)
        if db == "embl":    return self._embl_search(query, db_type, max_results)
        if db == "uniprot": return self._uniprot_search(query, max_results)
        raise ValueError(f"Unknown database: {db}")

    def fetch(self, accessions, db="ncbi", db_type="nucleotide"):
        if db == "ncbi":    return self._ncbi_fetch(accessions, db_type)
        if db == "embl":    return self._embl_fetch(accessions)
        if db == "uniprot": return self._uniprot_fetch(accessions)
        raise ValueError(f"Unknown database: {db}")

    # ── NCBI ────────────────────────────────────────────────
    def _ncbi_search(self, query, db_type, max_results):
        db = "protein" if db_type == "protein" else "nucleotide"
        params = urllib.parse.urlencode({"db": db, "term": query,
            "retmax": max_results, "retmode": "json", "email": EMAIL})
        data = self._json(f"{NCBI_BASE}/esearch.fcgi?{params}")
        ids = data.get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []
        params2 = urllib.parse.urlencode({"db": db, "id": ",".join(ids),
            "retmode": "json", "email": EMAIL})
        summary = self._json(f"{NCBI_BASE}/esummary.fcgi?{params2}")
        results = []
        for uid in ids:
            doc = summary.get("result", {}).get(uid, {})
            results.append({
                "accession": doc.get("accessionversion", uid),
                "title":     doc.get("title", "N/A"),
                "organism":  doc.get("organism", "N/A"),
                "length":    doc.get("slen", "N/A"),
                "database":  "ncbi", "db_type": db_type, "uid": uid,
            })
        return results

    def _ncbi_fetch(self, accessions, db_type):
        db = "protein" if db_type == "protein" else "nucleotide"
        params = urllib.parse.urlencode({"db": db, "id": ",".join(accessions),
            "rettype": "fasta", "retmode": "text", "email": EMAIL})
        return self._text(f"{NCBI_BASE}/efetch.fcgi?{params}")

    # ── EMBL ────────────────────────────────────────────────
    def _embl_search(self, query, db_type, max_results):
        params = urllib.parse.urlencode({"query": query, "result": "sequence",
            "limit": max_results, "format": "json"})
        try:
            data = self._json(f"{EMBL_BASE}/search?{params}")
        except Exception:
            return []
        return [{
            "accession": h.get("accession", ""),
            "title":     h.get("description", "N/A"),
            "organism":  h.get("scientific_name", "N/A"),
            "length":    h.get("sequence_length", "N/A"),
            "database":  "embl", "db_type": db_type,
        } for h in data.get("summaries", [])]

    def _embl_fetch(self, accessions):
        return self._text(f"{EMBL_BASE}/fasta/{','.join(accessions)}")

    # ── BOLD Systems ─────────────────────────────────────────
    def bold_search(self, taxon, marker="COI-5P", geo="", max_results=30):
        params = {"taxon": taxon, "marker": marker}
        if geo:
            params["geo"] = geo
        url = f"{BOLD_BASE}/specimen?{urllib.parse.urlencode(params)}&format=json"
        try:
            data = self._json(url)
        except Exception:
            return []
        records = data if isinstance(data, list) else data.get("bold_records", {}).values()
        results = []
        for rec in list(records)[:max_results]:
            tid = rec.get("taxonomy", {})
            results.append({
                "process_id": rec.get("processid", ""),
                "accession":  rec.get("genbank_accession", rec.get("processid", "")),
                "title":      tid.get("species", {}).get("taxon", {}).get("name", "N/A"),
                "organism":   tid.get("species", {}).get("taxon", {}).get("name", "N/A"),
                "country":    rec.get("collection_event", {}).get("country", "N/A"),
                "marker":     marker,
                "database":   "bold",
            })
        return results

    def bold_fetch(self, process_ids):
        ids = "|".join(process_ids)
        url = f"{BOLD_BASE}/sequence?ids={urllib.parse.quote(ids)}"
        return self._text(url)

    # ── UniProt ──────────────────────────────────────────────
    def _uniprot_search(self, query, max_results):
        params = urllib.parse.urlencode({"query": query, "format": "json",
            "size": max_results, "fields": "accession,protein_name,organism_name,length"})
        try:
            data = self._json(f"{UNIPROT_BASE}/search?{params}")
        except Exception:
            return []
        results = []
        for e in data.get("results", []):
            prot = e.get("proteinDescription", {}).get("recommendedName", {}).get("fullName", {}).get("value", "N/A")
            results.append({
                "accession": e.get("primaryAccession", ""),
                "title":     prot,
                "organism":  e.get("organism", {}).get("scientificName", "N/A"),
                "length":    e.get("sequence", {}).get("length", "N/A"),
                "database":  "uniprot", "db_type": "protein",
            })
        return results

    def _uniprot_fetch(self, accessions):
        parts = []
        for acc in accessions:
            try:
                parts.append(self._text(f"{UNIPROT_BASE}/{acc}.fasta"))
                time.sleep(0.1)
            except Exception:
                continue
        return "\n".join(parts)

    # ── HTTP helpers ─────────────────────────────────────────
    def _json(self, url):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())

    def _text(self, url):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode()

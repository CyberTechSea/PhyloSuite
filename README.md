# PhyloSuite

**An integrated phylogenetic analysis pipeline** — fetch sequences, align, select substitution models, infer trees, and generate publication-ready reports. All from a single local web interface.

> Created by the original author of [WinModelTest](https://sourceforge.net/projects/winmodeltest/) (2015).

---

## What PhyloSuite does

PhyloSuite combines three tools that do not exist together anywhere else:

| Module | What it does |
|---|---|
| **End-to-End Pipeline** | Fetch → Align → Model selection → IQ-TREE inference → Report |
| **Comparative Dashboard** | Compare model selection across multiple datasets with agreement metrics |
| **PhyloWizard Reports** | Publication-ready PDF, Methods section text, commands for 5 inference tools |

---

## Quick Start

### Option A — Standalone executable (no Python required)

Download the appropriate binary from [Releases](../../releases):

| Platform | File |
|---|---|
| Windows | `PhyloSuite-win.exe` |
| Linux   | `PhyloSuite-linux` |
| macOS   | `PhyloSuite-mac` |

Double-click (Windows) or run from terminal (Linux/macOS). The browser opens automatically at `http://127.0.0.1:5000`.

### Option B — Run from source

```bash
git clone https://github.com/YOUR_USERNAME/PhyloSuite.git
cd PhyloSuite
pip install -r requirements.txt
python backend/launch.py
```

---

## External Tools (optional but recommended)

PhyloSuite includes a built-in Python model selection engine. For publication-quality results, install:

| Tool | Purpose | URL |
|---|---|---|
| ModelTest-NG | ML model selection | https://github.com/ddarriba/modeltest |
| IQ-TREE 2 | Tree inference | http://www.iqtree.org |
| MAFFT | Multiple alignment | https://mafft.cbrc.jp |
| MUSCLE | Multiple alignment | https://www.drive5.com/muscle |

Place binaries in your system PATH. PhyloSuite auto-detects them at startup.

See [docs/INSTALL_TOOLS.md](docs/INSTALL_TOOLS.md) for platform-specific instructions.

---

## Features

### 1. Full Pipeline
- Upload FASTA / NEXUS / PHYLIP alignments (up to 100 MB)
- Fetch sequences directly from NCBI GenBank, EMBL-ENA, BOLD Systems, UniProt
- Paste raw FASTA in the browser
- Configurable alignment (MAFFT / MUSCLE / passthrough)
- Model selection: AIC, AICc, BIC, hLRT, parameter importances, Akaike weights
- Tree inference with IQ-TREE 2 (UFBoot support)
- Automatic report generation

### 2. Model Selection Details
- 88 DNA models (22 base matrices × rate/freq combinations) or 84 protein models
- Full hLRT cascade with chi-squared p-values
- Parameter importances (Akaike-weight-based)
- Model-averaged parameter estimates
- Supports ascertainment bias correction (Lewis, Felsenstein, Stamatakis)
- Template modes: RAxML, MrBayes, PhyML, PAUP\*
- 3 / 5 / 7 / 11 / 203 substitution scheme subsets

### 3. Database Integration
- **NCBI GenBank**: esearch + esummary + efetch (nucleotide + protein)
- **EMBL-ENA**: REST API search and FASTA fetch
- **BOLD Systems**: barcode search (COI-5P, ITS, rbcL, matK, 16S) by taxon + geography
- **UniProt**: protein search and per-accession FASTA fetch

### 4. Comparative Dashboard
- Select any 2+ completed jobs
- Side-by-side model comparison (AIC / AICc / BIC / hLRT)
- Criterion agreement score per dataset
- Visual concordance overview

### 5. Reports
- **Methods section** — auto-written paragraph for your manuscript, including citations
- **Tool commands** — ready-to-paste strings for IQ-TREE 2, RAxML, MrBayes, PhyML, PAUP\*
- **PDF report** — dataset summary, best models, parameter importances, top-20 BIC table (requires `reportlab`)
- **Export**: JSON, CSV, plain text

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/pipeline/upload` | POST | Upload alignment file |
| `/api/pipeline/run` | POST | Start full pipeline |
| `/api/pipeline/modeltest-only` | POST | Run model selection only |
| `/api/pipeline/compare` | POST | Compare multiple jobs |
| `/api/database/search` | POST | Search NCBI/EMBL/UniProt |
| `/api/database/fetch` | POST | Fetch sequences by accession |
| `/api/database/bold-search` | POST | Search BOLD Systems |
| `/api/database/bold-fetch` | POST | Fetch BOLD sequences |
| `/api/jobs/` | GET | List all jobs |
| `/api/jobs/<id>` | GET | Job status (lightweight) |
| `/api/jobs/<id>/full` | GET | Full job data including results |
| `/api/report/generate/<id>` | POST | Generate report |
| `/api/report/download/<id>/pdf` | GET | Download PDF |
| `/api/report/methods/<id>` | GET | Methods text + commands |
| `/api/report/export/<id>/<fmt>` | GET | Export (json/csv/txt) |
| `/health` | GET | Server health + tool status |

---

## Development

```bash
# Install dev dependencies
pip install -r requirements.txt pytest pytest-cov

# Run tests
pytest tests/ -v

# Run with debug mode
python backend/app.py

# Build executables
python build/build.py --platform all
```

### Project Structure

```
PhyloSuite/
├── backend/
│   ├── app.py              Flask application factory
│   ├── launch.py           Standalone executable entry point
│   ├── api/                REST API blueprints
│   ├── core/               Job manager, sequence parser, tool checker, DB fetcher
│   └── pipeline/           Step-by-step pipeline modules
├── frontend/
│   ├── templates/          Jinja2 HTML template
│   └── static/             CSS and JavaScript
├── build/
│   └── build.py            PyInstaller build script
├── tests/
│   └── test_core.py        Unit tests
├── docs/
│   └── INSTALL_TOOLS.md    External tool installation guide
└── .github/
    └── workflows/
        └── ci-release.yml  CI + auto-release workflow
```

---

## Built-in vs. ModelTest-NG Engine

| Feature | Built-in Python | ModelTest-NG |
|---|---|---|
| Log-likelihood | Composite (approximate) | Full ML optimization |
| Models | 88 DNA / 84 protein | Up to 1624 |
| AIC / AICc / BIC | ✓ | ✓ |
| hLRT | ✓ | ✓ |
| Parameter importances | ✓ | ✓ |
| Publication suitable | With disclaimer | ✓ |
| External binary required | No | Yes |

The built-in engine is suitable for exploration and development. Install ModelTest-NG for final analyses.

---

## Citation

If you use PhyloSuite in published work, please cite:

> Francesco Paolo Patti (2026). PhyloSuite: an integrated phylogenetic analysis pipeline. GitHub: https://github.com/YOUR_USERNAME/PhyloSuite (https://github.com/CyberTechSea/PhyloSuite)

And the underlying tools you used:

> Darriba D, et al. (2020) ModelTest-NG. *Mol Biol Evol* 37(1):291–294.  
> Minh BQ, et al. (2020) IQ-TREE 2. *Mol Biol Evol* 37(5):1530–1534.

---

## License

MIT License — see [LICENSE](LICENSE).

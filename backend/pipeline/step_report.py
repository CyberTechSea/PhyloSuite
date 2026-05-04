"""
Step Report
Generates:
  • Publication-ready PDF report
  • Methods section text (copy-paste into manuscript)
  • Command strings for IQ-TREE, RAxML, MrBayes, PAUP*, PhyML
  • Plain text summary
"""

import json, textwrap
from datetime import datetime
from pathlib import Path


class StepReport:
    def __init__(self, config):
        self.results_base = Path(config["RESULTS_FOLDER"])

    def run(self, job, opts):
        results_dir = Path(job["results_dir"])
        txt = self.generate_text_report(job)
        txt_path = results_dir / "report.txt"
        txt_path.write_text(txt)

        methods = self.generate_methods_text(job)
        commands = self.generate_commands(job)

        result = {
            "txt_path":  str(txt_path),
            "pdf_path":  None,  # PDF requires reportlab (optional)
            "methods":   methods,
            "commands":  commands,
        }

        # Try PDF generation (requires reportlab)
        try:
            pdf_path = self._generate_pdf(job, results_dir)
            result["pdf_path"] = str(pdf_path)
            result["pdf_available"] = True
        except ImportError:
            result["pdf_available"] = False
            result["pdf_message"] = "Install reportlab for PDF: pip install reportlab"
        except Exception as e:
            result["pdf_available"] = False
            result["pdf_message"] = str(e)

        return result

    # ── Methods text ────────────────────────────────────────
    def generate_methods_text(self, job):
        mt = job.get("modeltest_result", {})
        iq = job.get("iqtree_result", {})
        si = job.get("seq_info", {}) or mt.get("dataset", {})
        al = job.get("align_result", {})
        engine = mt.get("engine", "builtin-python")

        bic_model  = mt.get("best_model_bic",  {}).get("name", "N/A")
        aic_model  = mt.get("best_model_aic",  {}).get("name", "N/A")
        aicc_model = mt.get("best_model_aicc", {}).get("name", "N/A")
        hlrt_model = mt.get("hlrt", {}).get("selected_model", "N/A")
        n_seqs     = si.get("n_sequences", "N/A")
        n_sites    = si.get("n_sites",     "N/A")
        datatype   = si.get("datatype",    "DNA")
        n_tested   = mt.get("n_models_tested", "N/A")

        aligner_text = ""
        if al and al.get("method") not in (None, "passthrough"):
            aligner_text = (
                f"Sequences were aligned using {al['method'].upper()} "
                f"with default parameters. "
            )

        iqtree_text = ""
        if iq and iq.get("available"):
            boot = "1000 ultrafast bootstrap replicates"
            iqtree_text = (
                f"Phylogenetic inference was performed with IQ-TREE 2 "
                f"(Minh et al., 2020) under the {bic_model} model using {boot}. "
            )

        engine_ref = ("ModelTest-NG (Darriba et al., 2020)"
                      if "modeltest-ng" in engine
                      else "a composite-likelihood model selection engine")

        text = textwrap.dedent(f"""
            METHODS — Model Selection and Phylogenetic Analysis

            The dataset comprised {n_seqs} {datatype} sequences of {n_sites} aligned
            positions. {aligner_text}Substitution model selection was performed using
            {engine_ref}. A total of {n_tested} candidate models were evaluated.
            Model fit was assessed using the Akaike Information Criterion (AIC),
            the corrected AIC (AICc), the Bayesian Information Criterion (BIC), and
            hierarchical likelihood ratio tests (hLRT).

            The best-fit models selected by each criterion were:
              • AIC:  {aic_model}
              • AICc: {aicc_model}
              • BIC:  {bic_model}  (recommended for phylogenetics)
              • hLRT: {hlrt_model}

            {iqtree_text}

            References:
              Darriba D et al. (2020) ModelTest-NG. Mol Biol Evol 37(1):291–294.
              Minh BQ et al. (2020) IQ-TREE 2. Mol Biol Evol 37(5):1530–1534.
        """).strip()
        return text

    # ── Command strings for downstream tools ────────────────
    def generate_commands(self, job):
        mt = job.get("modeltest_result", {})
        si = job.get("seq_info", {}) or mt.get("dataset", {})
        seq_file = job.get("seq_file", "alignment.fasta")
        bic_model = mt.get("best_model_bic", {}).get("name", "GTR+G")
        aic_model = mt.get("best_model_aic", {}).get("name", "GTR+G")

        # Convert model name to tool-specific syntax
        raxml_model = self._model_to_raxml(bic_model)
        mrbayes_block = self._model_to_mrbayes(bic_model)
        phyml_args = self._model_to_phyml(bic_model, seq_file)

        return {
            "iqtree2": f"iqtree2 -s {seq_file} -m {bic_model} -B 1000 -T AUTO",
            "raxml":   f"raxmlHPC -s {seq_file} -m {raxml_model} -n RESULT -p 12345",
            "mrbayes": f"# In MrBayes block:\n{mrbayes_block}",
            "phyml":   phyml_args,
            "paup":    f"# PAUP*:\nbegin paup;\n  set criterion=likelihood;\n  lset nst=6 rates=gamma;\n  hsearch;\nend;",
        }

    def _model_to_raxml(self, model):
        base = model.split("+")[0]
        mods = model.upper()
        if "GTR" in base:
            suffix = "CAT"
            if "+G" in mods: suffix = "GAMMA"
            if "+I" in mods: suffix = "GAMMAI" if "+G" in mods else "GTRCATI"
            return f"GTR{suffix}"
        return "GTRGAMMA"

    def _model_to_mrbayes(self, model):
        base = model.split("+")[0].upper()
        nst  = "6" if "GTR" in base else "2" if base in ("HKY","K80","TrN") else "1"
        rates = "invgamma" if "+I+G" in model else "gamma" if "+G" in model else "propinv" if "+I" in model else "equal"
        return f"  lset nst={nst} rates={rates};\n  mcmcp ngen=1000000 samplefreq=1000;"

    def _model_to_phyml(self, model, seq_file):
        base = model.split("+")[0].upper()
        m_flag = "GTR" if "GTR" in base else "HKY85" if "HKY" in base else "JC69"
        c_flag = "4"
        a_flag = "e" if "+G" in model else "0"
        return f"phyml -i {seq_file} -m {m_flag} -a {a_flag} -c {c_flag} -o tlr"

    # ── Text report ─────────────────────────────────────────
    def generate_text_report(self, job):
        mt = job.get("modeltest_result", {})
        iq = job.get("iqtree_result", {})
        si = job.get("seq_info", {}) or mt.get("dataset", {})
        models = mt.get("models", [])
        pi = mt.get("parameter_importances", {})

        sep = "=" * 70
        lines = [
            sep,
            "  PHYLOSUITE — ANALYSIS REPORT",
            f"  Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            sep, "",
            "DATASET",
            f"  Sequences : {si.get('n_sequences', 'N/A')}",
            f"  Sites     : {si.get('n_sites', 'N/A')}",
            f"  Data type : {si.get('datatype', 'N/A')}",
            f"  Format    : {si.get('format', 'N/A')}",
            f"  Gaps      : {si.get('gap_pct', 'N/A')}%",
            "",
            "BEST MODELS",
            f"  AIC  : {mt.get('best_model_aic',{}).get('name','N/A')}",
            f"  AICc : {mt.get('best_model_aicc',{}).get('name','N/A')}",
            f"  BIC  : {mt.get('best_model_bic',{}).get('name','N/A')}  ← recommended",
            f"  hLRT : {mt.get('hlrt',{}).get('selected_model','N/A')}",
            "",
            "PARAMETER IMPORTANCES (AIC weights)",
            f"  +Γ  Gamma rates   : {pi.get('gamma', 'N/A')}",
            f"  +I  Invariant sites: {pi.get('inv_sites', 'N/A')}",
            f"  +Γ+I Both         : {pi.get('gamma_inv', 'N/A')}",
            f"  +F  Freq estimated : {pi.get('frequencies', 'N/A')}",
            "",
            f"TOP 20 MODELS (BIC ranking)",
            f"{'#':<4} {'Model':<20} {'lnL':>12} {'K':>4} {'BIC':>14} {'ΔBIC':>10} {'wBIC':>8}",
            "-" * 76,
        ]

        bic_ranked = sorted(models, key=lambda m: m.get("BIC", 0))[:20]
        for i, m in enumerate(bic_ranked, 1):
            lines.append(
                f"{i:<4} {m.get('name',''):<20} {m.get('lnL',0):>12.4f} "
                f"{m.get('K',0):>4} {m.get('BIC',0):>14.4f} "
                f"{m.get('delta_BIC',0):>10.4f} {m.get('weight_BIC',0):>8.6f}"
            )

        if iq and iq.get("available"):
            lines += ["", "PHYLOGENETIC TREE (IQ-TREE 2)",
                      f"  Model used : {iq.get('model_used','N/A')}",
                      f"  lnL        : {iq.get('lnL','N/A')}",
                      f"  BIC score  : {iq.get('bic','N/A')}"]

        lines += ["", sep]
        return "\n".join(lines)

    # ── PDF generation (optional reportlab) ─────────────────
    def _generate_pdf(self, job, results_dir):
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                        Table, TableStyle, HRFlowable)

        pdf_path = results_dir / "report.pdf"
        doc = SimpleDocTemplate(str(pdf_path), pagesize=A4,
                                leftMargin=2*cm, rightMargin=2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)

        styles = getSampleStyleSheet()
        style_h1 = ParagraphStyle("h1", parent=styles["Heading1"],
                                   fontSize=16, textColor=colors.HexColor("#0a2540"))
        style_h2 = ParagraphStyle("h2", parent=styles["Heading2"],
                                   fontSize=12, textColor=colors.HexColor("#1a6b8a"))
        style_body = styles["Normal"]
        style_mono = ParagraphStyle("mono", parent=styles["Code"],
                                    fontSize=8, fontName="Courier")

        mt = job.get("modeltest_result", {})
        si = job.get("seq_info", {}) or mt.get("dataset", {})
        models = mt.get("models", [])
        pi = mt.get("parameter_importances", {})
        commands = self.generate_commands(job)
        methods  = self.generate_methods_text(job)

        story = [
            Paragraph("PhyloSuite Analysis Report", style_h1),
            Paragraph(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", style_body),
            HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0a2540")),
            Spacer(1, 0.3*cm),

            Paragraph("1. Dataset Summary", style_h2),
            Table([
                ["Parameter", "Value"],
                ["Sequences",  str(si.get("n_sequences", "N/A"))],
                ["Sites",      str(si.get("n_sites", "N/A"))],
                ["Data type",  str(si.get("datatype", "N/A"))],
                ["Gap %",      str(si.get("gap_pct", "N/A"))],
                ["Engine",     str(mt.get("engine", "N/A"))],
                ["Models tested", str(mt.get("n_models_tested", "N/A"))],
            ], colWidths=[5*cm, 10*cm],
            style=TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0a2540")),
                ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
                ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE",   (0,0), (-1,-1), 9),
                ("GRID",       (0,0), (-1,-1), 0.5, colors.HexColor("#cccccc")),
                ("BACKGROUND", (0,1), (-1,-1), colors.HexColor("#f7f9fc")),
                ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f0f4f8")]),
            ])),
            Spacer(1, 0.4*cm),

            Paragraph("2. Best-Fit Models", style_h2),
            Table([
                ["Criterion", "Best Model", "Score"],
                ["AIC",  mt.get("best_model_aic",  {}).get("name","N/A"), str(round(mt.get("best_model_aic",  {}).get("AIC",  0), 2))],
                ["AICc", mt.get("best_model_aicc", {}).get("name","N/A"), str(round(mt.get("best_model_aicc", {}).get("AICc", 0), 2))],
                ["BIC ★",mt.get("best_model_bic",  {}).get("name","N/A"), str(round(mt.get("best_model_bic",  {}).get("BIC",  0), 2))],
                ["hLRT", mt.get("hlrt",{}).get("selected_model","N/A"), "—"],
            ], colWidths=[3*cm, 6*cm, 6*cm],
            style=TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1a6b8a")),
                ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
                ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE",   (0,0), (-1,-1), 9),
                ("GRID",       (0,0), (-1,-1), 0.5, colors.HexColor("#cccccc")),
                ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f0f4f8")]),
            ])),
            Spacer(1, 0.4*cm),

            Paragraph("3. Parameter Importances (AIC weights)", style_h2),
            Table([
                ["Parameter", "Importance"],
                ["+Γ Gamma rates",    str(pi.get("gamma","N/A"))],
                ["+I Invariant sites",str(pi.get("inv_sites","N/A"))],
                ["+Γ+I Combined",     str(pi.get("gamma_inv","N/A"))],
                ["+F Empirical freq.",str(pi.get("frequencies","N/A"))],
            ], colWidths=[8*cm, 7*cm],
            style=TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#2d6a4f")),
                ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
                ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE",   (0,0), (-1,-1), 9),
                ("GRID",       (0,0), (-1,-1), 0.5, colors.HexColor("#cccccc")),
                ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f0f4f8")]),
            ])),
            Spacer(1, 0.4*cm),

            Paragraph("4. Top 15 Models by BIC", style_h2),
        ]

        bic_rows = [["#","Model","lnL","K","BIC","ΔBIC","wBIC"]]
        for i, m in enumerate(sorted(models, key=lambda x: x.get("BIC",0))[:15], 1):
            bic_rows.append([str(i), m.get("name",""), f"{m.get('lnL',0):.2f}",
                             str(m.get("K","")), f"{m.get('BIC',0):.2f}",
                             f"{m.get('delta_BIC',0):.2f}", f"{m.get('weight_BIC',0):.5f}"])

        story.append(Table(bic_rows, colWidths=[1.2*cm,4.5*cm,3*cm,1.5*cm,3.5*cm,2.5*cm,2.5*cm],
            style=TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#343a40")),
                ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
                ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTNAME",   (0,1), (-1,-1), "Courier"),
                ("FONTSIZE",   (0,0), (-1,-1), 8),
                ("GRID",       (0,0), (-1,-1), 0.3, colors.HexColor("#cccccc")),
                ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f0f4f8")]),
                ("BACKGROUND", (0,1), (-1,1), colors.HexColor("#d4edda")),
            ])))

        story += [
            Spacer(1, 0.4*cm),
            Paragraph("5. Methods Section", style_h2),
            Paragraph(methods.replace("\n", "<br/>"), style_body),
            Spacer(1, 0.4*cm),
            Paragraph("6. Commands for Downstream Tools", style_h2),
        ]
        for tool, cmd in commands.items():
            story.append(Paragraph(f"<b>{tool.upper()}</b>", style_body))
            story.append(Paragraph(cmd.replace("\n","<br/>").replace(" ","&nbsp;"), style_mono))
            story.append(Spacer(1, 0.2*cm))

        doc.build(story)
        return pdf_path

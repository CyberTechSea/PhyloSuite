"""PhyloSuite — Unit Tests"""

import math, os, sys, tempfile, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from core.seq_parser import SeqParser
from pipeline.step_modeltest import StepModelTest

FASTA = """>S1\nATGCATGCATGCATGCATGCATGC\n>S2\nATGCATGCATGCATGCATGCATGT\n>S3\nTTGCATGCATGCATGCATGCATGC\n>S4\nATGCATGCATGCATGCATGCATGA\n"""
FASTA_UNEQUAL = """>S1\nATGC\n>S2\nATGCATGC\n"""
NEXUS = """#NEXUS\nBEGIN DATA;\n  DIMENSIONS NTAX=3 NCHAR=20;\n  FORMAT DATATYPE=DNA;\n  MATRIX\n    S1 ATGCATGCATGCATGCATGC\n    S2 ATGCATGCATGCATGCATGC\n    S3 TTGCATGCATGCATGCATGA\n  ;\nEND;\n"""


class TestSeqParser:
    def _tmp(self, content, suffix='.fasta'):
        f = tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False)
        f.write(content); f.close(); return f.name

    def test_fasta_basic(self):
        p = SeqParser().parse(self._tmp(FASTA))
        assert p['n_sequences'] == 4
        assert p['n_sites'] == 24
        assert p['format'] == 'FASTA'
        assert p['datatype'] == 'DNA'

    def test_unequal_raises(self):
        with pytest.raises(ValueError, match="Unequal"):
            SeqParser().parse(self._tmp(FASTA_UNEQUAL))

    def test_nexus(self):
        p = SeqParser().parse(self._tmp(NEXUS, '.nex'))
        assert p['n_sequences'] == 3
        assert p['format'] == 'NEXUS'

    def test_protein_detection(self):
        prot = ">P1\nMELQADEFGHIKLMNPQRSTVWY\n>P2\nMELQADEFGHIKLMNPQRSTVWY\n"
        p = SeqParser().parse(self._tmp(prot))
        assert p['datatype'] == 'protein'

    def test_gap_pct(self):
        gapped = ">S1\nATGC----\n>S2\nATGC----\n"
        p = SeqParser().parse(self._tmp(gapped))
        assert p['gap_pct'] == 50.0


class TestStepModelTest:
    def _config(self):
        tmp = tempfile.mkdtemp()
        return {'RESULTS_FOLDER': tmp, 'UPLOAD_FOLDER': tmp, 'JOBS_FOLDER': tmp}

    def _job(self, config):
        seq_dir = tempfile.mkdtemp()
        res_dir = tempfile.mkdtemp()
        fname = os.path.join(seq_dir, 'test.fasta')
        with open(fname, 'w') as f: f.write(FASTA)
        parser = SeqParser()
        info = parser.parse(fname)
        return {'seq_file': fname, 'results_dir': res_dir, 'seq_info': info}

    def test_run_returns_models(self):
        cfg = self._config()
        job = self._job(cfg)
        mt = StepModelTest(cfg)
        result = mt._run_builtin(job, {}, __import__('pathlib').Path(job['results_dir']))
        assert len(result['models']) > 0
        assert 'best_model_aic' in result
        assert 'best_model_bic' in result

    def test_weights_sum_to_one(self):
        cfg = self._config()
        job = self._job(cfg)
        mt = StepModelTest(cfg)
        result = mt._run_builtin(job, {}, __import__('pathlib').Path(job['results_dir']))
        total = sum(m['weight_AIC'] for m in result['models'])
        assert abs(total - 1.0) < 1e-3

    def test_models_sorted_by_aic(self):
        cfg = self._config()
        job = self._job(cfg)
        mt = StepModelTest(cfg)
        result = mt._run_builtin(job, {}, __import__('pathlib').Path(job['results_dir']))
        aics = [m['AIC'] for m in result['models']]
        assert aics == sorted(aics)

    def test_hlrt_structure(self):
        cfg = self._config()
        job = self._job(cfg)
        mt = StepModelTest(cfg)
        result = mt._run_builtin(job, {}, __import__('pathlib').Path(job['results_dir']))
        hlrt = result['hlrt']
        assert 'tests' in hlrt
        assert 'selected_model' in hlrt
        for t in hlrt['tests']:
            assert 'p_value' in t
            assert 'rejected' in t

    def test_param_importances(self):
        cfg = self._config()
        job = self._job(cfg)
        mt = StepModelTest(cfg)
        result = mt._run_builtin(job, {}, __import__('pathlib').Path(job['results_dir']))
        pi = result['parameter_importances']
        assert 'gamma' in pi
        assert 'inv_sites' in pi
        total = pi['gamma'] + pi['inv_sites'] + pi['gamma_inv']
        assert 0.0 <= total <= 1.0 + 1e-3

    def test_aic_formula(self):
        lnL, K = -1000.0, 5
        aic = -2 * lnL + 2 * K
        assert abs(aic - 2010.0) < 0.001

    def test_bic_formula(self):
        lnL, K, n = -1000.0, 5, 500
        bic = -2 * lnL + K * math.log(n)
        assert abs(bic - (2000 + 5 * math.log(500))) < 0.001

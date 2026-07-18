"""Tests unitaires pour anu_tool.py."""
import sys
from pathlib import Path

import pytest

# Ajout du répertoire tool/ au path
sys.path.insert(0, str(Path(__file__).parent.parent / "tool"))
from anu_tool import detect_mode, _read_p2_score, DEFAULT_MODE


# ── detect_mode ───────────────────────────────────────────────────────────────

class TestDetectMode:
    def test_architecture_keyword(self):
        assert detect_mode("conçois une architecture microservices") == 1

    def test_code_keyword(self):
        assert detect_mode("debug ce script python") == 2

    def test_teacher_keyword(self):
        assert detect_mode("explique le fonctionnement de SSH") == 3

    def test_protocol_keyword(self):
        assert detect_mode("rédige la procédure de déploiement") == 4

    def test_auditor_keyword(self):
        assert detect_mode("audit sécurité de la VM hermes") == 5

    def test_writer_keyword(self):
        assert detect_mode("rédige un rapport sur les performances") == 6

    def test_researcher_keyword(self):
        assert detect_mode("compare les solutions de monitoring") == 7

    def test_no_match_returns_default(self):
        assert detect_mode("bonjour") == DEFAULT_MODE

    def test_case_insensitive(self):
        assert detect_mode("ARCHITECTURE système") == 1

    def test_empty_topic(self):
        assert detect_mode("") == DEFAULT_MODE


# ── _read_p2_score ────────────────────────────────────────────────────────────

class TestReadP2Score:
    def test_missing_file_returns_zero(self, tmp_path):
        assert _read_p2_score(tmp_path) == 0.0

    def test_score_as_float(self, tmp_path):
        p2 = tmp_path / "p2.json"
        p2.write_text('{"score": 8.5}', encoding="utf-8")
        assert _read_p2_score(tmp_path) == 8.5

    def test_score_as_dict_averages(self, tmp_path):
        p2 = tmp_path / "p2.json"
        p2.write_text(
            '{"score": {"factualite": 8, "couverture": 6, "coherence": 7, '
            '"risques": 9, "clarte": 7}}',
            encoding="utf-8",
        )
        result = _read_p2_score(tmp_path)
        assert result == pytest.approx(7.4, abs=0.1)

    def test_invalid_json_returns_zero(self, tmp_path):
        p2 = tmp_path / "p2.json"
        p2.write_text("not json", encoding="utf-8")
        assert _read_p2_score(tmp_path) == 0.0

    def test_missing_score_key_returns_zero(self, tmp_path):
        p2 = tmp_path / "p2.json"
        p2.write_text('{"status": "completed"}', encoding="utf-8")
        assert _read_p2_score(tmp_path) == 0.0

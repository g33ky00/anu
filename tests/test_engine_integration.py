"""Tests d'intégration engine.py — nécessitent un backend LLM actif.
Marqués skip par défaut pour CI sans credentials.
Lancer manuellement : pytest tests/test_engine_integration.py -m integration
"""
import sys
import argparse
from pathlib import Path

import pytest

ENGINE_PATH = Path(__file__).parent.parent / "scripts" / "engine.py"


def _load_engine():
    import importlib.util
    spec = importlib.util.spec_from_file_location("anu_engine", ENGINE_PATH)
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    return engine


@pytest.mark.integration
@pytest.mark.skipif(not ENGINE_PATH.exists(), reason="engine.py introuvable")
class TestEngineIntegration:
    def test_engine_imports(self):
        engine = _load_engine()
        assert hasattr(engine, "run_passes")
        assert hasattr(engine, "llm_generate")
        assert hasattr(engine, "make_run_dir")

    def test_resolved_model(self):
        engine = _load_engine()
        model = engine._resolved_model("auto")
        assert model  # non vide
        assert "/" in model or model == "auto"  # format vendor/model

    def test_run_passes_dry_run(self, tmp_path):
        """Teste run_passes sans appel LLM réel (topic vide → erreur contrôlée).
        TODO: Hermes — ajouter paramètre dry_run dans engine.py pour CI propre.
        """
        # Ce test est intentionnellement minimal
        # L'implémentation complète nécessite un mock de llm_generate
        pass  # TODO: Hermes — mocker llm_generate pour test unitaire

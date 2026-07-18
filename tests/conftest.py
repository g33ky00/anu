"""Configuration pytest pour les tests ANU."""
import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: tests nécessitant un backend LLM actif"
    )

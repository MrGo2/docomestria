"""Shared pytest configuration."""

from __future__ import annotations


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: tests that run the heavy upstream engines (LiteParse, Docling).",
    )

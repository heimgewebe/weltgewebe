#!/usr/bin/env python3
"""Smoke test that the shared requirements test module has a valid entrypoint."""

import runpy


def test_requirements_test_module_imports() -> None:
    runpy.run_module(
        "scripts.docmeta.tests.test_report_lifecycle_requirements",
        run_name="not_main",
    )

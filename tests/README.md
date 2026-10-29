[![Tests](https://github.com/algra4/ha-edilkamin/actions/workflows/tests.yml/badge.svg)](https://github.com/algra4/ha-edilkamin/actions/workflows/tests.yml)
[![Dependabot Updates](https://github.com/algra4/ha-edilkamin/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/algra4/ha-edilkamin/actions/workflows/dependabot/dependabot-updates)
[![CodeQL](https://github.com/algra4/ha-edilkamin/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/algra4/ha-edilkamin/actions/workflows/github-code-scanning/codeql)


# Testing Guide

This guide explains how to set up the testing environment and run tests for the Edilkamin Home Assistant integration.

## Prerequisites

### Installing uv

[uv](https://github.com/astral-sh/uv) is a fast Python package manager and resolver. Install it using one of the following methods:

**Linux/macOS:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Installation

### Using uv (Recommended)

Install all dependencies declared in pyproject.toml, the dev dependency-group is installed by default:

```bash
uv sync
```

CI tests Home Assistant 2025.5.0 and 2025.9.0 on Python 3.13, plus
2026.10.4 on Python 3.14. It installs the `test` dependency group together
with the selected HA version instead of syncing the default `dev` group,
which pins HA 2025.5.0. For 2025.9.0, CI also constrains `pycares<5`:
its `aiodns` version imports APIs removed by pycares 5.

## Running Tests

### Run all tests

```bash
uv run pytest
```

### Run tests with verbose output

```bash
uv run pytest -v
```

### Run a specific test file

```bash
uv run pytest tests/test_coordinator_safety.py
```

Note: The repository no longer uses requirements*.txt files. Runtime dependencies are installed by Home Assistant from custom_components/edilkamin/manifest.json. Development and test dependencies are defined in pyproject.toml and managed via uv.

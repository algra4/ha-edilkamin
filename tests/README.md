# Testing Guide

This guide explains how to set up the testing environment and run tests for the Edilkamin Home Assistant integration.

## Prerequisites

### Installing uv

[uv](https://github.com/astral-sh/uv) is a fast Python package installer and resolver. Install it using one of the following methods:

**Linux/macOS:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Installation

### Option 1: Using uv (Recommended)

Install all test dependencies using uv:

```bash
uv pip install -r requirements.test.txt
```

## Running Tests

### Run all tests

```bash
un run pytest
```

### Run tests with verbose output

```bash
uv run pytest -v
```

### Run a specific test file

```bash
uv run pytest tests/test_coordinator_safety.py
```

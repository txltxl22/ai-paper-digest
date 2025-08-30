#!/bin/bash

# Exit on any error
set -e

uv run python -m pytest tests/

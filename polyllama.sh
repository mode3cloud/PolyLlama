#!/bin/bash

# PolyLlama Launcher - Delegates to Python CLI
# This is a thin wrapper that passes all arguments to the Python implementation

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Execute the Python CLI with all arguments
exec python3 -m builder.cli "$@"
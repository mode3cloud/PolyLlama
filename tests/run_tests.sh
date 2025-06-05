#!/bin/bash

# PolyLlama Generation Test Runner
# Runs all tests to verify dynamic generation works correctly

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "🧪 PolyLlama Generation Test Suite"
echo "=================================="
echo ""
echo "📂 Working directory: $(pwd)"
echo "🐍 Python version: $(python3 --version)"
echo ""

# Check dependencies
echo "🔍 Checking dependencies..."

if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ Python3 is required but not installed"
    exit 1
fi

if ! python3 -c "import yaml" >/dev/null 2>&1; then
    echo "❌ PyYAML is required. Install with: pip install pyyaml"
    exit 1
fi

echo "✅ All dependencies found"
echo ""

# Run the main test suite
echo "🚀 Running main test suite..."
echo ""

if python3 tests/generation.py; then
    echo ""
    echo "🚀 Running edge case tests..."
    echo ""
    
    if python3 tests/edge_cases.py; then
        echo ""
        echo "🎉 All tests completed successfully!"
        exit 0
    else
        echo ""
        echo "❌ Edge case tests failed!"
        exit 1
    fi
else
    echo ""
    echo "❌ Main tests failed!"
    exit 1
fi
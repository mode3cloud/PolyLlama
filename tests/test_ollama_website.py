#!/usr/bin/env python3
"""
Simple runner for ollama.com website tests
Can be run directly: python tests/test_ollama_website.py
"""

import subprocess
import sys

if __name__ == "__main__":
    # Run the tests using pytest
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        "tests/test_ollama_search.py::TestOllamaWebsite", 
        "-v"
    ])
    sys.exit(result.returncode)
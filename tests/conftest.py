"""
Pytest configuration file that sets up the Python path for testing.
"""
import sys
from pathlib import Path

# Add the project root to the Python path so we can import from 'stack'
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Also add agent-controller directly to the path
agent_controller_path = project_root / "stack" / "agent-controller"
if agent_controller_path.exists():
    sys.path.insert(0, str(agent_controller_path))
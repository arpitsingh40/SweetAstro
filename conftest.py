"""
Pytest configuration and root path resolution for SweetAstro.
"""

import sys
from pathlib import Path

root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir.parent))

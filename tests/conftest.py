# pytest configuration to ensure 'orca_agent' is importable
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

"""Ensure the project root is on sys.path so `from src.…` imports work."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

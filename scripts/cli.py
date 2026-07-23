#!/usr/bin/env python3
"""Unified CLI for pipixia-doctor. Delegates to scripts.doctor."""
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.doctor import main  # noqa: E402

if __name__ == '__main__':
    main()

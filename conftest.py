"""Pytest/unittest support — makes `src/` importable for tests.

Imported automatically by pytest. For plain `unittest discover`, see
``tests/_setup.py``, which each test module imports explicitly.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

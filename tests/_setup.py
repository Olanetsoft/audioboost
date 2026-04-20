"""Puts `src/` on sys.path so tests can import the app modules without install,
and silences ResourceWarnings from subprocess pipe teardown in integration runs.
"""

import os
import sys
import warnings

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.abspath(os.path.join(_HERE, "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

warnings.filterwarnings("ignore", category=ResourceWarning)

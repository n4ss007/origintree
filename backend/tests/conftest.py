import sys
from pathlib import Path

# Let the tests import the backend modules the same way the server does.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

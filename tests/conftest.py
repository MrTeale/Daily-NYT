import os
import sys

# Make `import handler` resolve to src/handler.py without installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

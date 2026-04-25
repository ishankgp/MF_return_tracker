import runpy
import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, ".pydeps"))

runpy.run_path(os.path.join(ROOT, "app.py"), run_name="__main__")
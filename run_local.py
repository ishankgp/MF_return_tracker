import runpy
import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


runpy.run_path(os.path.join(ROOT, "app.py"), run_name="__main__")
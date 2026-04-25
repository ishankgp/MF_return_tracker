import runpy
import sys

ROOT = r"D:\Github clones\mutual_funds"
sys.path.insert(0, ROOT)
sys.path.insert(0, ROOT + r"\\.pydeps")

runpy.run_path(ROOT + r"\\app.py", run_name="__main__")
import sys
from pathlib import Path

# Change this import path to wherever your DbMeta package is installed.
# Example:
# from dbmeta import FolderDB

DATA_PATH = Path(__file__).parent / "data" / "synthetic_runs"

def show_structure():
    for run in sorted(DATA_PATH.iterdir())[:5]:
        print(run.name, "->", ", ".join(p.name for p in run.iterdir()))

if __name__ == "__main__":
    show_structure()
    print()
    print("DbMeta:")
    print('db = FolderDB(base_path="data/synthetic_runs", base_metadata="metadata.json")')
    print("Available tables should correspond to the top-level keys in metadata.json.")

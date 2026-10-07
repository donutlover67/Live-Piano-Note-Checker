"""Starts the program. Works two ways:

    python -m evenkeys                  (from the project folder)
    python evenkeys/__main__.py         (or the Run button in VS Code)
"""

import sys
from pathlib import Path

# When this file is run directly, Python doesn't know it belongs to the "evenkeys"
# package, so it can't find the other modules. Adding the project folder (the folder
# that CONTAINS the evenkeys package) to the search path fixes that.
if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evenkeys.cli import main

main()

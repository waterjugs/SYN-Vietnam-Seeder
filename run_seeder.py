"""PyInstaller entry point (it can't start from a package's __main__)."""

import sys

from seeder.__main__ import main

sys.exit(main())

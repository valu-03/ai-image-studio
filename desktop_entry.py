"""Executable entry point for AI Image Studio."""

import multiprocessing
import sys

from studio.desktop import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())


#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Trieflow LLC
# SPDX-License-Identifier: GPL-3.0-or-later
"""Forward explicit audited packaging inputs; signing/publication belong to release CI."""
from pathlib import Path
import subprocess
import sys

if __name__ == '__main__':
    builder=Path(__file__).resolve().parents[2]/'packaging/windows/msix/build_msix.py'
    raise SystemExit(subprocess.call([sys.executable,str(builder),*sys.argv[1:]]))

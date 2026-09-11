# Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
"""Compatibility command for verifying the complete archive-derived stage."""
import sys
from locked_windows_deps import main
sys.argv.insert(1, 'verify')
main()

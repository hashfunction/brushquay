# SPDX-FileCopyrightText: 2026 Trieflow LLC
# SPDX-License-Identifier: GPL-3.0-or-later
# Package from the reviewed source checkout after the native runtime is audited.
# Do not generate a default Store identity or install packaging tools into the app.
message(STATUS "Bristlune MSIX requires explicit identity, SDK tool lock and audited runtime inventory; no package is generated during native installation")

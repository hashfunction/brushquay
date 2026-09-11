/* SPDX-FileCopyrightText: 2026 Trieflow LLC
 * SPDX-License-Identifier: GPL-3.0-or-later */
#include "KisBrushQuayWorkspaceLayouts.h"
bool compileNativeWorkspaceLayout(QMainWindow &window,QString &error)
{
    return KisBrushQuayWorkspaceLayouts::arrange(window,KisBrushQuayWorkspaceLayouts::Kind::Illustration,error);
}

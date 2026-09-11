/* SPDX-FileCopyrightText: 2026 Trieflow LLC
 * SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef KIS_EXPORT_PRESET_CODEC_H
#define KIS_EXPORT_PRESET_CODEC_H
#include "KisExportPreset.h"
#include <kis_types.h>
#include <kritaui_export.h>
class KRITAUI_EXPORT KisExportPresetCodec {
public:
    static KisExportPresetResult capture(const QUuid &,const QString &name,const QString &mime,const QString &extension,const KisPropertiesConfigurationSP &,KisExportPreset &);
    static KisExportPresetResult restore(const KisExportPreset &,KisPropertiesConfigurationSP &);
};
#endif

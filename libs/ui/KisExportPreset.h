/* SPDX-FileCopyrightText: 2026 Trieflow LLC
 * SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef KIS_EXPORT_PRESET_H
#define KIS_EXPORT_PRESET_H
#include <QByteArray>
#include <QString>
#include <QStringList>
#include <QUuid>
#include <QVariantMap>

// The domain has only Qt dependencies so it can be tested without loading an editor.
enum class KisExportPresetError {
    None, InvalidPreset, UnsupportedSchema, InvalidStore, NotLoaded,
    ReadFailed, WriteFailed, Conflict, Busy, Cancelled
};
struct KisExportPresetResult {
    KisExportPresetError code = KisExportPresetError::None;
    QString message;
    QString recoveryPath;
    bool ok() const { return code == KisExportPresetError::None; }
};
struct KisExportPreset {
    static constexpr int Schema = 1;
    QUuid id;
    QString name;
    QString mimeType;
    QString extension;
    // Only reviewed, format-specific settings. No arbitrary plug-in state or image data.
    QVariantMap properties;
    KisExportPresetResult validate() const;
    KisExportPresetResult serialize(QByteArray &output) const;
    static KisExportPresetResult deserialize(const QByteArray &data, KisExportPreset &output);
    static QStringList supportedMimeTypes();
};
#endif

/* SPDX-FileCopyrightText: 2026 Trieflow LLC
 * SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef KIS_EXPORT_PRESET_STORE_H
#define KIS_EXPORT_PRESET_STORE_H
#include "KisExportPreset.h"
#include <QList>
#include <functional>
#include <optional>
class KisExportPresetStore {
public:
    explicit KisExportPresetStore(QString path = {});
    KisExportPresetResult load();
    KisExportPresetResult save(const KisExportPreset &preset, const std::function<bool()> &cancelled = {});
    KisExportPresetResult remove(const QUuid &id, const std::function<bool()> &cancelled = {});
    const QList<KisExportPreset> &presets() const { return m_presets; }
    std::optional<KisExportPreset> find(const QUuid &id) const;
    QString path() const { return m_path; }
private:
    KisExportPresetResult persist(const QList<KisExportPreset> &, const std::function<bool()> &);
    KisExportPresetResult quarantine(KisExportPresetResult error, const QByteArray &data) const;
    QString m_path;
    QByteArray m_loadedBytes;
    bool m_existed = false;
    bool m_loaded = false;
    QList<KisExportPreset> m_presets;
};
#endif

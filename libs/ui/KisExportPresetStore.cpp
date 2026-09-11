/* SPDX-FileCopyrightText: 2026 Trieflow LLC
 * SPDX-License-Identifier: GPL-3.0-or-later */
#include "KisExportPresetStore.h"
#include <algorithm>
#include <utility>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLockFile>
#include <QSaveFile>
#include <QSet>
#include <QStandardPaths>

namespace {
constexpr qint64 MaxBytes = 2 * 1024 * 1024;
KisExportPresetResult read(const QString &path, bool &exists, QByteArray &data)
{
    const QFileInfo info(path);
    exists = info.exists();
    if (info.isSymLink() || (exists && !info.isFile())) return {KisExportPresetError::ReadFailed, "Preset store is not a regular file: " + path, {}};
    if (!exists) { data.clear(); return {}; }
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly) || file.size() > MaxBytes) return {KisExportPresetError::ReadFailed, "Cannot read preset store or it exceeds 2 MiB: " + path, {}};
    data = file.read(MaxBytes + 1);
    if (data.size() > MaxBytes || file.error() != QFileDevice::NoError) return {KisExportPresetError::ReadFailed, "Could not read complete preset store: " + path, {}};
    return {};
}
}
KisExportPresetStore::KisExportPresetStore(QString path)
    : m_path(path.isEmpty() ? QStandardPaths::writableLocation(QStandardPaths::AppDataLocation) + "/brushquay/export-presets-v1.json" : std::move(path)) {}
KisExportPresetResult KisExportPresetStore::quarantine(KisExportPresetResult error, const QByteArray &data) const
{
    // Preserve the exact rejected bytes; leave the original in place and all writes blocked.
    const auto recovery = m_path + ".recovery-" + QUuid::createUuid().toString(QUuid::WithoutBraces);
    QFile file(recovery);
    if (file.open(QIODevice::WriteOnly | QIODevice::NewOnly) && file.write(data) == data.size() && file.flush()) error.recoveryPath = recovery;
    error.message += " Original preserved at " + m_path + ". Repair or move it explicitly, then reload before editing presets.";
    return error;
}
KisExportPresetResult KisExportPresetStore::load()
{
    m_loaded = false;
    bool exists = false; QByteArray data;
    auto result = read(m_path, exists, data); if (!result.ok()) return result;
    QList<KisExportPreset> presets;
    if (exists) {
        QJsonParseError parse; const auto doc = QJsonDocument::fromJson(data, &parse); const auto obj = doc.object();
        if (parse.error != QJsonParseError::NoError || !doc.isObject()) return quarantine({KisExportPresetError::InvalidStore, "Malformed export preset store.", {}}, data);
        if (obj.value("schema") != QJsonValue(KisExportPreset::Schema)) return quarantine({KisExportPresetError::UnsupportedSchema, "Unsupported export preset store version.", {}}, data);
        if (obj.size() != 2 || !obj.value("presets").isArray() || obj.value("presets").toArray().size() > 1000) return quarantine({KisExportPresetError::InvalidStore, "Invalid preset list.", {}}, data);
        QSet<QUuid> ids;
        for (const auto &entry : obj.value("presets").toArray()) {
            KisExportPreset p;
            result = KisExportPreset::deserialize(QJsonDocument(entry.toObject()).toJson(QJsonDocument::Compact), p);
            if (!entry.isObject() || !result.ok() || ids.contains(p.id)) return quarantine({KisExportPresetError::InvalidStore, "Invalid or duplicate preset entry: " + result.message, {}}, data);
            ids.insert(p.id); presets.append(p);
        }
    }
    m_presets = presets; m_loadedBytes = data; m_existed = exists; m_loaded = true;
    return {};
}
std::optional<KisExportPreset> KisExportPresetStore::find(const QUuid &id) const
{
    for (const auto &p : m_presets) if (p.id == id) return p;
    return std::nullopt;
}
KisExportPresetResult KisExportPresetStore::save(const KisExportPreset &preset, const std::function<bool()> &cancelled)
{
    if (!m_loaded) return {KisExportPresetError::NotLoaded, "Load or recover the preset store before writing.", {}};
    const auto result = preset.validate(); if (!result.ok()) return result;
    auto next = m_presets;
    auto it = std::find_if(next.begin(), next.end(), [&](const KisExportPreset &p) { return p.id == preset.id; });
    if (it == next.end()) next.append(preset); else *it = preset;
    return persist(next, cancelled);
}
KisExportPresetResult KisExportPresetStore::remove(const QUuid &id, const std::function<bool()> &cancelled)
{
    if (!m_loaded) return {KisExportPresetError::NotLoaded, "Load or recover the preset store before writing.", {}};
    auto next = m_presets;
    next.erase(std::remove_if(next.begin(), next.end(), [&](const KisExportPreset &p) { return p.id == id; }), next.end());
    return persist(next, cancelled);
}
KisExportPresetResult KisExportPresetStore::persist(const QList<KisExportPreset> &next, const std::function<bool()> &cancelled)
{
    if (cancelled && cancelled()) return {KisExportPresetError::Cancelled, "Preset write cancelled.", {}};
    if (!QDir().mkpath(QFileInfo(m_path).absolutePath())) return {KisExportPresetError::WriteFailed, "Cannot create preset directory: " + m_path, {}};
    QLockFile lock(m_path + ".lock");
    if (!lock.tryLock(0)) return {KisExportPresetError::Busy, "Another process is editing presets. Reload and retry.", {}};
    auto unchanged = [&]() {
        bool exists = false; QByteArray bytes;
        auto result = read(m_path, exists, bytes);
        return result.ok() && exists == m_existed && bytes == m_loadedBytes;
    };
    if (!unchanged()) { m_loaded = false; return {KisExportPresetError::Conflict, "Preset store changed. Reload before editing.", {}}; }
    QJsonArray entries;
    for (const auto &p : next) { QByteArray bytes; auto result = p.serialize(bytes); if (!result.ok()) return result; entries.append(QJsonDocument::fromJson(bytes).object()); }
    const auto data = QJsonDocument(QJsonObject{{"schema", KisExportPreset::Schema}, {"presets", entries}}).toJson(QJsonDocument::Indented);
    if (data.size() > MaxBytes || next.size() > 1000) return {KisExportPresetError::WriteFailed, "Preset store is full.", {}};
    QSaveFile file(m_path); file.setDirectWriteFallback(false);
    if (!file.open(QIODevice::WriteOnly) || file.write(data) != data.size()) return {KisExportPresetError::WriteFailed, "Could not stage preset store: " + m_path, {}};
    if (cancelled && cancelled()) { file.cancelWriting(); return {KisExportPresetError::Cancelled, "Preset write cancelled.", {}}; }
    // Cooperating writers are serialized by QLockFile. The byte check detects stale UI state;
    // it is not a cross-process compare-and-swap against noncooperating filesystem writers.
    if (!unchanged()) { file.cancelWriting(); m_loaded = false; return {KisExportPresetError::Conflict, "Preset store changed during write. Reload before editing.", {}}; }
    if (!file.commit()) return {KisExportPresetError::WriteFailed, "Could not commit preset store: " + m_path, {}};
    m_presets = next; m_loadedBytes = data; m_existed = true; return {};
}

/* SPDX-FileCopyrightText: 2026 Trieflow LLC
 * SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef KIS_EXPORT_FILE_TRANSACTION_H
#define KIS_EXPORT_FILE_TRANSACTION_H
#include <QByteArray>
#include <QString>
#include <QStringList>
#include <QList>
#include <QPair>
#include <functional>
#include <optional>
#include <stdexcept>

struct KisExportFileIdentity {
    quint64 device=0, file=0, size=0;
    QByteArray sha256;
    bool operator==(const KisExportFileIdentity &other) const {
        return device==other.device && file==other.file && size==other.size && sha256==other.sha256;
    }
    bool operator!=(const KisExportFileIdentity &other) const { return !(*this==other); }
    bool sameFile(const KisExportFileIdentity &other) const { return device==other.device && file==other.file; }
};
struct KisExportDestination {
    QString path;
    std::optional<KisExportFileIdentity> existing;
    bool overwriteConfirmed=false;
    QList<QPair<QString,KisExportFileIdentity>> directories;
    // Capture before asking for replacement consent; the job receives an immutable copy.
    static KisExportDestination capture(const QString &path);
    void validate() const;
};
struct KisExportFileOutcome {
    bool published=false;
    bool cancelled=false;
    QString outputPath, stagedPath, previousPath, error, warning;
};
class KisExportFileTransaction {
public:
    KisExportFileTransaction(const KisExportDestination &, const QStringList &protectedPaths);
    QString stagedPath() const { return m_staged; }
    KisExportFileOutcome finish(bool exportSucceeded, const std::function<bool()> &cancelled = {});
private:
    void checkProtected() const;
    const KisExportDestination m_destination;
    QList<QPair<QString,std::optional<KisExportFileIdentity>>> m_protected;
    QString m_staged, m_previous;
    bool m_finished=false;
};
#endif

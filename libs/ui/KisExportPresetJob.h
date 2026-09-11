/* SPDX-FileCopyrightText: 2026 Trieflow LLC
 * SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef KIS_EXPORT_PRESET_JOB_H
#define KIS_EXPORT_PRESET_JOB_H
#include "KisExportPreset.h"
#include "KisExportFileTransaction.h"
#include <QObject>
#include <QPointer>
#include <QSize>
#include <kritaui_export.h>
#include <atomic>
#include <memory>
class KisDocument;
Q_DECLARE_METATYPE(KisExportFileOutcome)
class KRITAUI_EXPORT KisExportPresetJob : public QObject {
    Q_OBJECT
public:
    KisExportPresetJob(KisDocument *,KisExportPreset,KisExportDestination,QObject *parent=nullptr);
    ~KisExportPresetJob() override;
    void start();
public Q_SLOTS:
    void cancel();
Q_SIGNALS:
    void finished(KisExportFileOutcome result);
private:
    void complete(bool success,const QString &error={},const QString &warning={});
    QPointer<KisDocument> m_document;
    const KisExportPreset m_preset;
    const KisExportDestination m_destination;
    std::shared_ptr<std::atomic_bool> m_cancelled;
    std::shared_ptr<KisExportFileTransaction> m_transaction;
    QMetaObject::Connection m_completion;
    QSize m_expectedSize;
    bool m_started=false,m_finishing=false;
};
#endif

/* SPDX-FileCopyrightText: 2026 Trieflow LLC
 * SPDX-License-Identifier: GPL-3.0-or-later */
#include "KisExportPresetJob.h"
#include "KisExportPresetCodec.h"
#include "KisDocument.h"
#include "kis_file_layer.h"
#include "KisReferenceImage.h"
#include "flake/KisReferenceImagesLayer.h"
#include <kis_layer_utils.h>
#include <QFutureWatcher>
#include <QImageReader>
#include <QtConcurrentRun>
#include <utility>
namespace {
struct Prepared {
    std::shared_ptr<KisExportFileTransaction> transaction;
    QString error;
};
}
KisExportPresetJob::KisExportPresetJob(KisDocument *document,KisExportPreset preset,KisExportDestination destination,QObject *parent)
    :QObject(parent),m_document(document),m_preset(std::move(preset)),m_destination(std::move(destination)),m_cancelled(std::make_shared<std::atomic_bool>(false))
{
    qRegisterMetaType<KisExportFileOutcome>();
    if (document) connect(document,&QObject::destroyed,this,[this] {
        cancel();
        if (m_transaction && !m_finishing) complete(false,"The source document closed during export; publication was cancelled.");
    });
}
KisExportPresetJob::~KisExportPresetJob() { cancel(); disconnect(m_completion); }
void KisExportPresetJob::cancel() { m_cancelled->store(true); }
void KisExportPresetJob::start()
{
    if (m_started) return; m_started=true;
    if (!m_document || !m_document->image()) { complete(false,"The source document is no longer open."); return; }
    KisPropertiesConfigurationSP configuration;
    auto validation=KisExportPresetCodec::restore(m_preset,configuration);
    if (!validation.ok()) { complete(false,validation.message); return; }
    QStringList sources{m_document->path()};
    KisLayerUtils::recursiveApplyNodes(m_document->image()->root(),[&](KisNodeSP node) {
        if (auto *file=dynamic_cast<KisFileLayer *>(node.data())) sources.append(file->path());
    });
    if (const auto references=m_document->referenceImagesLayer()) {
        for (const auto *reference:references->referenceImages()) if (!reference->filename().isEmpty()) sources.append(reference->filename());
    }
    sources.removeDuplicates();
    auto *watcher=new QFutureWatcher<Prepared>(this);
    connect(watcher,&QFutureWatcher<Prepared>::finished,this,[this,watcher,configuration] {
        const auto result=watcher->result(); watcher->deleteLater(); m_transaction=result.transaction;
        if (!result.error.isEmpty()) { complete(false,result.error); return; }
        if (!m_document || m_cancelled->load()) { complete(false,"Export cancelled before rendering."); return; }
        m_expectedSize=m_document->image()->bounds().size();
        m_completion=connect(m_document,&KisDocument::sigCompleteBackgroundSaving,this,
            [this](const KritaUtils::ExportFileJob &job,KisImportExportErrorCode status,const QString &error,const QString &warning) {
                if (m_transaction && job.filePath==m_transaction->stagedPath()) {
                    if (status.isCancelled()) cancel();
                    complete(status.isOk(),status.isOk()?QString():error,warning);
                }
            });
        // Use the established asynchronous snapshot/export path. Keep native format warnings.
        const bool started=m_document->exportDocument(m_transaction->stagedPath(),m_preset.mimeType.toLatin1(),false,true,configuration);
        if (!started && !m_finishing) complete(false,"The native export could not start; no destination was published.");
    });
    const auto destination=m_destination;
    watcher->setFuture(QtConcurrent::run([destination,sources] {
        Prepared result;
        try { result.transaction=std::make_shared<KisExportFileTransaction>(destination,sources); }
        catch (const std::exception &error) { result.error=QString::fromUtf8(error.what()); }
        return result;
    }));
}
void KisExportPresetJob::complete(bool success,const QString &error,const QString &warning)
{
    if (m_finishing) return; m_finishing=true; disconnect(m_completion);
    if (!m_transaction) {
        KisExportFileOutcome result; result.outputPath=m_destination.path; result.error=error; result.cancelled=m_cancelled->load();
        Q_EMIT finished(result); return;
    }
    const auto transaction=m_transaction; const auto token=m_cancelled; const auto expected=m_expectedSize; const auto mime=m_preset.mimeType;
    auto *watcher=new QFutureWatcher<KisExportFileOutcome>(this);
    connect(watcher,&QFutureWatcher<KisExportFileOutcome>::finished,this,[this,watcher] {
        const auto result=watcher->result(); watcher->deleteLater(); Q_EMIT finished(result);
    });
    watcher->setFuture(QtConcurrent::run([transaction,token,expected,mime,success,error,warning] {
        bool valid=success; QString message=error;
        if (valid && !token->load()) {
            QImageReader reader(transaction->stagedPath());
            const auto format=reader.format(); const auto required=mime=="image/png"?QByteArray("png"):QByteArray("jpeg");
            if (format!=required || reader.size()!=expected || reader.read().isNull()) {
                valid=false; message="Exported image could not be decoded with the expected format and dimensions: "+transaction->stagedPath();
            }
        }
        auto result=transaction->finish(valid,[token] { return token->load(); });
        if (!message.isEmpty() && !result.error.contains(message)) result.error+=(result.error.isEmpty()?QString():"\n")+message;
        result.warning=warning;
        return result;
    }));
}

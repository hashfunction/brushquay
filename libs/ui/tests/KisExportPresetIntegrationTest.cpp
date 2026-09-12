/* SPDX-FileCopyrightText: 2026 Trieflow LLC
 * SPDX-License-Identifier: GPL-3.0-or-later */
#include <QtTest>
#include <QImageReader>
#include <QPushButton>
#include <QLineEdit>
#include <QListWidget>
#include "dialogs/KisExportPresetDialog.h"
#include <QTemporaryDir>
#include <QFile>
#include <QFileInfo>
#include <QScopedPointer>
#include <KisDocument.h>
#include <KisPart.h>
#include <KisImportExportManager.h>
#include <KoColorSpaceRegistry.h>
#include <KoColorProfile.h>
#include <KoJsonTrader.h>
#include <kis_image.h>
#include <kis_paint_layer.h>
#include <kis_paint_device.h>
#include <kis_config_widget.h>
#include <testui.h>
#include "KisExportPresetCodec.h"
#include "KisExportPresetJob.h"

namespace {
QString pluginPathAtApplicationStartup;
void recordPluginPathAtApplicationStartup()
{
    pluginPathAtApplicationStartup=qEnvironmentVariable("KRITA_PLUGIN_PATH");
}
}
Q_COREAPP_STARTUP_FUNCTION(recordPluginPathAtApplicationStartup)

class KisExportPresetIntegrationTest : public QObject {
    Q_OBJECT
    static KisImageSP image()
    {
        const auto *space=KoColorSpaceRegistry::instance()->rgb8();
        KisImageSP result=new KisImage(nullptr,32,24,space,"BrushQuay generated fixture");
        KisPaintLayerSP layer=new KisPaintLayer(result,"Own generated solid color",OPACITY_OPAQUE_U8);
        layer->paintDevice()->fill(result->bounds(),KoColor(QColor(32,96,160),space));
        result->addNode(layer,result->root()); result->waitForDone(); return result;
    }
private Q_SLOTS:
    void initTestCase()
    {
#ifdef Q_OS_WIN
        const QString pluginPath=QCoreApplication::applicationDirPath();
        QCOMPARE(pluginPathAtApplicationStartup,pluginPath);
        QCOMPARE(qEnvironmentVariable("KRITA_PLUGIN_PATH"),pluginPath);
        QStringList discovered;
        for (const auto &plugin:KoJsonTrader::instance()->query("Krita/FileFilter",QString())) {
            discovered << QFileInfo(plugin.fileName()).fileName();
        }
        for (const auto &plugin:QStringList{"kritapngexport.dll","kritajpegexport.dll"}) {
            QVERIFY2(QFileInfo::exists(pluginPath+"/"+plugin),qPrintable(QStringLiteral("Missing built export plugin: ")+plugin));
            QVERIFY2(discovered.contains(plugin),qPrintable(QStringLiteral("Export plugin absent from startup cache: ")+plugin+"; discovered: "+discovered.join(", ")));
        }
        for (const auto &mime:QStringList{"image/png","image/jpeg"}) {
            QScopedPointer<KisImportExportFilter> filter(KisImportExportManager::filterForMimeType(mime,KisImportExportManager::Export));
            QVERIFY2(filter,qPrintable(QStringLiteral("Native export filter did not load: ")+mime));
        }
#endif
    }
    void nativeOptionsRoundTrip_data()
    {
        QTest::addColumn<QString>("mime"); QTest::newRow("PNG")<<"image/png"; QTest::newRow("JPEG")<<"image/jpeg";
    }
    void nativeOptionsRoundTrip()
    {
        QFETCH(QString,mime);
        QScopedPointer<KisImportExportFilter> filter(KisImportExportManager::filterForMimeType(mime,KisImportExportManager::Export));
        QVERIFY(filter); auto config=filter->defaultConfiguration(); QVERIFY(config);
        KoColor color(QColor(40,80,120),KoColorSpaceRegistry::instance()->rgb8()); color.setOpacity(qreal(0.5));
        config->setProperty("transparencyFillcolor",QVariant::fromValue(color));
        const QString key=mime=="image/png"?"compression":"quality"; config->setProperty(key,mime=="image/png"?8:91);
        KisExportPreset p; auto result=KisExportPresetCodec::capture(QUuid::createUuid(),QString::fromUtf8("水彩 preset"),mime,mime=="image/png"?"png":"jpg",config,p);
        QVERIFY2(result.ok(),qPrintable(result.message)); QByteArray bytes; QVERIFY(p.serialize(bytes).ok());
        KisExportPreset copy; QVERIFY(KisExportPreset::deserialize(bytes,copy).ok());
        KisPropertiesConfigurationSP restored; result=KisExportPresetCodec::restore(copy,restored);
        QVERIFY2(result.ok(),qPrintable(result.message)); QCOMPARE(restored->getProperty(key),config->getProperty(key));
        QCOMPARE(restored->getColor("transparencyFillcolor"),color);
        QScopedPointer<KisConfigWidget> widget(filter->createConfigurationWidget(nullptr)); QVERIFY(widget);
        KisImportExportManager::fillStaticExportConfigurationProperties(restored,image());
        widget->setConfiguration(restored); QCOMPARE(widget->configuration()->getInt(key),config->getInt(key));
    }
    void unknownFormatCannotChangeConfiguration()
    {
        KisExportPreset p; p.id=QUuid::createUuid(); p.name="Unsafe"; p.mimeType="application/x-krita"; p.extension="kra";
        KisPropertiesConfigurationSP output=new KisPropertiesConfiguration(); output->setProperty("sentinel",true);
        QVERIFY(!KisExportPresetCodec::restore(p,output).ok()); QVERIFY(output->getBool("sentinel"));
    }
    void actualDialogSaveSelectAndApplyNeverStartsExport()
    {
        QTemporaryDir dir; QScopedPointer<KisDocument> document(KisPart::instance()->createDocument());
        document->setCurrentImage(image()); document->setModified(true);
        QSignalSpy exported(document.data(),&KisDocument::sigCompleteBackgroundSaving);
        KisExportPresetDialog dialog(document.data(),nullptr,dir.filePath("presets.json"));
        auto *name=dialog.findChild<QLineEdit *>("exportPresetName"); QVERIFY(name); name->setText(QString::fromUtf8("水彩 work"));
        auto *save=dialog.findChild<QPushButton *>("saveExportPreset"); QVERIFY(save); QVERIFY(save->isEnabled()); save->click();
        auto *list=dialog.findChild<QListWidget *>("savedExportPresets"); QVERIFY(list); QCOMPARE(list->count(),1);
        list->setCurrentRow(0); dialog.findChild<QPushButton *>("chooseExportDestination")->click();
        QVERIFY(dialog.selectedPreset()); QCOMPARE(dialog.selectedPreset()->name,name->text());
        QCOMPARE(exported.size(),0); QVERIFY(document->path().isEmpty()); QVERIFY(document->isModified());
    }
    void actualDialogFailedLoadBlocksSaveAndDelete()
    {
        QTemporaryDir dir; const auto path=dir.filePath("broken.json"); QFile original(path);
        QVERIFY(original.open(QIODevice::WriteOnly)); original.write("broken but recoverable"); original.close();
        QScopedPointer<KisDocument> document(KisPart::instance()->createDocument()); document->setCurrentImage(image());
        KisExportPresetDialog dialog(document.data(),nullptr,path);
        auto *save=dialog.findChild<QPushButton *>("saveExportPreset"); auto *remove=dialog.findChild<QPushButton *>("deleteExportPreset");
        QVERIFY(save); QVERIFY(remove); QVERIFY(!save->isEnabled()); QVERIFY(!remove->isEnabled()); save->click(); remove->click();
        QVERIFY(original.open(QIODevice::ReadOnly)); QCOMPARE(original.readAll(),QByteArray("broken but recoverable"));
    }
    void realPngLateOwnerIsPreservedAtCompletion()
    {
        QTemporaryDir dir; const QString path=QFileInfo(dir.path()).canonicalFilePath()+"/late.png";
        QScopedPointer<KisDocument> document(KisPart::instance()->createDocument()); document->setCurrentImage(image()); document->setFileBatchMode(true);
        QScopedPointer<KisImportExportFilter> filter(KisImportExportManager::filterForMimeType("image/png",KisImportExportManager::Export)); QVERIFY(filter);
        KisExportPreset preset; QVERIFY(KisExportPresetCodec::capture(QUuid::createUuid(),"PNG","image/png","png",filter->defaultConfiguration(),preset).ok());
        connect(document.data(),&KisDocument::sigCompleteBackgroundSaving,this,[path](const KritaUtils::ExportFileJob &,KisImportExportErrorCode,const QString &,const QString &) {
            QFile late(path); if (!late.open(QIODevice::WriteOnly|QIODevice::NewOnly)) qFatal("late owner fixture failed"); late.write("late owner bytes");
        });
        KisExportPresetJob job(document.data(),preset,KisExportDestination::capture(path)); QSignalSpy finished(&job,&KisExportPresetJob::finished);
        job.start(); QTRY_COMPARE_WITH_TIMEOUT(finished.size(),1,30000);
        auto result=qvariant_cast<KisExportFileOutcome>(finished.at(0).at(0)); QVERIFY(!result.published); QVERIFY(!result.error.isEmpty());
        QFile late(path); QVERIFY(late.open(QIODevice::ReadOnly)); QCOMPARE(late.readAll(),QByteArray("late owner bytes"));
        QImageReader staged(result.stagedPath); QVERIFY(!staged.read().isNull());
    }
    void closedSourceFinishesWithoutPublication()
    {
        QTemporaryDir dir; const QString path=QFileInfo(dir.path()).canonicalFilePath()+"/closed.png";
        auto *document=KisPart::instance()->createDocument(); document->setCurrentImage(image()); document->setFileBatchMode(true);
        QScopedPointer<KisImportExportFilter> filter(KisImportExportManager::filterForMimeType("image/png",KisImportExportManager::Export)); QVERIFY(filter);
        KisExportPreset preset; QVERIFY(KisExportPresetCodec::capture(QUuid::createUuid(),"PNG","image/png","png",filter->defaultConfiguration(),preset).ok());
        KisExportPresetJob job(document,preset,KisExportDestination::capture(path)); QSignalSpy finished(&job,&KisExportPresetJob::finished);
        job.start(); delete document;
        QTRY_COMPARE_WITH_TIMEOUT(finished.size(),1,30000);
        auto result=qvariant_cast<KisExportFileOutcome>(finished.at(0).at(0)); QVERIFY(!result.published); QVERIFY(result.cancelled); QVERIFY(!QFile::exists(path));
    }
    void generatedImageExportsWithoutChangingSource_data()
    {
        QTest::addColumn<QString>("mime"); QTest::newRow("PNG")<<"image/png"; QTest::newRow("JPEG")<<"image/jpeg";
    }
    void generatedImageExportsWithoutChangingSource()
    {
        QFETCH(QString,mime); QTemporaryDir dir; auto root=QFileInfo(dir.path()).canonicalFilePath();
        const QString source=root+"/source.kra"; QFile original(source); QVERIFY(original.open(QIODevice::WriteOnly)); original.write("original source bytes"); original.close();
        QScopedPointer<KisDocument> document(KisPart::instance()->createDocument()); document->setCurrentImage(image());
        document->setFileBatchMode(true); document->setPath(source); document->setModified(true);
        QScopedPointer<KisImportExportFilter> filter(KisImportExportManager::filterForMimeType(mime,KisImportExportManager::Export)); QVERIFY(filter);
        KisExportPreset p; QVERIFY(KisExportPresetCodec::capture(QUuid::createUuid(),"Generated export",mime,mime=="image/png"?"png":"jpg",filter->defaultConfiguration(),p).ok());
        const QString output=root+QString::fromUtf8("/水彩.")+p.extension;
        KisExportPresetJob job(document.data(),p,KisExportDestination::capture(output)); QSignalSpy finished(&job,&KisExportPresetJob::finished);
        job.start(); QTRY_COMPARE_WITH_TIMEOUT(finished.size(),1,30000);
        const auto result=qvariant_cast<KisExportFileOutcome>(finished.at(0).at(0));
        QVERIFY2(result.published,qPrintable(result.error)); QVERIFY2(result.error.isEmpty(),qPrintable(result.error));
        QImageReader reader(output); QCOMPARE(reader.size(),QSize(32,24)); QVERIFY(!reader.read().isNull());
        QCOMPARE(document->path(),source); QVERIFY(document->isModified());
        QVERIFY(original.open(QIODevice::ReadOnly)); QCOMPARE(original.readAll(),QByteArray("original source bytes"));
    }
};
KISTEST_MAIN(KisExportPresetIntegrationTest)
#include "KisExportPresetIntegrationTest.moc"

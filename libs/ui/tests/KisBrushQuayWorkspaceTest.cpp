/* SPDX-FileCopyrightText: 2026 Trieflow LLC
 * SPDX-License-Identifier: GPL-3.0-or-later */
#include <QtTest>
#include <QBuffer>
#include <QCryptographicHash>
#include <QDomDocument>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTemporaryDir>
#include <QSysInfo>
#include <QRegularExpression>
#include <KisMainWindow.h>
#include <KisPart.h>
#include <KisResourceModel.h>
#include <kis_workspace_resource.h>
#include <testui.h>
#include "KisBrushQuayWorkspaceLayouts.h"

class KisBrushQuayWorkspaceTest : public QObject {
    Q_OBJECT
private Q_SLOTS:
    void originalLayoutsSaveReloadAndRestore_data()
    {
        QTest::addColumn<int>("layout");
        QTest::newRow("Illustration")<<0; QTest::newRow("Inking")<<1;
    }
    void originalLayoutsSaveReloadAndRestore()
    {
        QFETCH(int,layout);
        const auto kind=static_cast<KisBrushQuayWorkspaceLayouts::Kind>(layout);
        QScopedPointer<KisMainWindow> window(KisPart::instance()->createMainWindow());
        QString error; QVERIFY2(KisBrushQuayWorkspaceLayouts::arrange(*window,kind,error),qPrintable(error));
        const auto state=window->saveState(); QVERIFY(!state.isEmpty());
        const QString name=KisBrushQuayWorkspaceLayouts::name(kind);
        KisWorkspaceResource resource("");resource.setName(name);resource.setDockerState(state);resource.setValid(true);
        QByteArray data;QBuffer saved(&data);QVERIFY(saved.open(QIODevice::WriteOnly));QVERIFY(resource.saveToDevice(&saved));saved.close();
        QDomDocument xml;QVERIFY(xml.setContent(data));QCOMPARE(xml.documentElement().tagName(),QString("Workspace"));
        QCOMPARE(xml.documentElement().attribute("version"),QString("1"));
        QVERIFY(xml.documentElement().firstChildElement("image").isNull());
        QVERIFY(xml.documentElement().firstChildElement("settings").firstChildElement().isNull());
        QVERIFY(!data.contains(QDir::homePath().toUtf8())); QVERIFY(!data.contains("file://"));
        // QMainWindow state stores docker/toolbar names as UTF-16, not source paths.
        const auto home=QDir::homePath(); const QByteArray home16(reinterpret_cast<const char *>(home.utf16()),home.size()*2);
        QVERIFY(!state.contains(home16));
        KisWorkspaceResource copy("");QBuffer loaded(&data);QVERIFY(loaded.open(QIODevice::ReadOnly));QVERIFY(copy.loadFromDevice(&loaded,nullptr));
        QCOMPARE(copy.name(),name);QCOMPARE(copy.dockerState(),state);QVERIFY(copy.valid());
        for (int i=0;i<3;++i) QVERIFY(window->restoreWorkspaceState(copy.dockerState()));
        auto *layers=window->findChild<QDockWidget *>("KisLayerBox"); QVERIFY(layers);QVERIFY(!layers->isHidden());
        QCOMPARE(window->dockWidgetArea(layers),Qt::RightDockWidgetArea);
        auto *color=window->findChild<QDockWidget *>("ColorSelectorNg");QVERIFY(color);
        QCOMPARE(color->isHidden(),layout==1);
        // Use the real resource model, refusing any same-name file replacement.
        KisResourceModel model(ResourceType::Workspaces);
        QBuffer importedBytes(&data);QVERIFY(importedBytes.open(QIODevice::ReadOnly));
        const QString filename="BrushQuay_"+name.section(' ',1)+".kws";
        auto imported=model.importResource(filename,&importedBytes,false);QVERIFY(imported);
        QVERIFY(model.indexForResource(imported).isValid());QCOMPARE(imported->name(),name);
        QVERIFY(!model.resourcesForFilename(filename).isEmpty());
        const auto directory=qEnvironmentVariable("BRUSHQUAY_WORKSPACE_OUTPUT");
        if (!directory.isEmpty()) {
#ifndef Q_OS_WIN
            QFAIL("Committed workspace generation must use the accepted Windows candidate, not this host");
#endif
            const auto sourceCommit=qEnvironmentVariable("BRUSHQUAY_WORKSPACE_SOURCE_COMMIT");
            QVERIFY(QRegularExpression("^[0-9a-f]{40}$").match(sourceCommit).hasMatch());
            QDir output(directory);QVERIFY(output.mkpath("."));
            QFile file(output.filePath(filename));QVERIFY(file.open(QIODevice::WriteOnly|QIODevice::NewOnly));QCOMPARE(file.write(data),data.size());file.close();
            QJsonObject record{{"schema",1},{"name",name},{"file",filename},{"author","Trieflow LLC"},{"license","CC0-1.0"},
                {"qtVersion",qVersion()},{"platform",QSysInfo::prettyProductName()},{"generatorSourceCommit",sourceCommit},
                {"sha256",QString::fromLatin1(QCryptographicHash::hash(data,QCryptographicHash::Sha256).toHex())},
                {"nativeSaveReloadRestorePassed",true},{"windowsVisualAcceptance",false}};
            QFile provenance(output.filePath(filename+".json"));QVERIFY(provenance.open(QIODevice::WriteOnly|QIODevice::NewOnly));
            const auto bytes=QJsonDocument(record).toJson();QCOMPARE(provenance.write(bytes),bytes.size());
            qInfo()<<"Original workspace source output:"<<file.fileName();
        }
    }
    void missingDockerDoesNotMutateLayout()
    {
        QMainWindow empty;empty.resize(1000,700);const auto before=empty.saveState();QString error;
        QVERIFY(!KisBrushQuayWorkspaceLayouts::arrange(empty,KisBrushQuayWorkspaceLayouts::Kind::Illustration,error));
        QVERIFY(!error.isEmpty());QCOMPARE(empty.saveState(),before);QCOMPARE(empty.size(),QSize(1000,700));
    }
};
KISTEST_MAIN(KisBrushQuayWorkspaceTest)
#include "KisBrushQuayWorkspaceTest.moc"

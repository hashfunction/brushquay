/* SPDX-FileCopyrightText: 2026 Trieflow LLC
 * SPDX-License-Identifier: GPL-3.0-or-later */
#include <QtTest>
#include <QStandardPaths>
#include <QFileInfo>
#include <QUrl>
#include <QFile>
#include <KisBrushQuayIdentity.h>
class KisBrushQuayIdentityTest : public QObject {
    Q_OBJECT
private Q_SLOTS:
    void isolatedApplicationDataAndConfiguration()
    {
        QCoreApplication::setApplicationName("krita"); QCoreApplication::setOrganizationName("");
        const auto upstream=QStandardPaths::writableLocation(QStandardPaths::AppDataLocation);
        QCoreApplication::setApplicationName("brushquay");
        const auto existingProfile=QStandardPaths::writableLocation(QStandardPaths::AppDataLocation);
        KisBrushQuayIdentity::apply();
        const auto product=QStandardPaths::writableLocation(QStandardPaths::AppDataLocation);
        QCOMPARE(product,existingProfile);
        QVERIFY(product!=upstream); QCOMPARE(QFileInfo(product).fileName(),QString("brushquay"));
        QCOMPARE(QCoreApplication::applicationName(),QString("brushquay"));
        QCOMPARE(QString::fromLatin1(KisBrushQuayIdentity::DisplayName),QString("Bristlune"));
        QCOMPARE(QCoreApplication::applicationVersion(),QString("1.0.1"));
        QCOMPARE(QCoreApplication::organizationDomain(),QString("trieflow.com"));
    }
    void compiledOriginalArtworkResources()
    {
        for (const auto &name : {":/bristlune.svg", ":/bristlune-banner.svg", ":/bristlune-splash.png"}) {
            QFile file(QString::fromLatin1(name)); QVERIFY2(file.open(QIODevice::ReadOnly),name);
            QVERIFY(file.size()>100);
            if (file.fileName().endsWith(".png")) QCOMPARE(file.read(8),QByteArray::fromHex("89504e470d0a1a0a"));
            else QVERIFY(file.readAll().contains("<svg"));
        }
    }
    void canonicalProductLinks()
    {
        for (const auto &url:{KisBrushQuayIdentity::ProductUrl,KisBrushQuayIdentity::PrivacyUrl,KisBrushQuayIdentity::SupportUrl}) {
            const QUrl parsed(QString::fromLatin1(url)); QCOMPARE(parsed.scheme(),QString("https")); QCOMPARE(parsed.host(),QString("bristlune.trieflow.com"));
        }
    }
};
QTEST_GUILESS_MAIN(KisBrushQuayIdentityTest)
#include "KisBrushQuayIdentityTest.moc"

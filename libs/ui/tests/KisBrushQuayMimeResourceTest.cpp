/* SPDX-FileCopyrightText: 2026 Trieflow LLC
 * SPDX-License-Identifier: GPL-3.0-or-later */
#include <QtTest>
#include <QFile>
#include <QMimeDatabase>
#include <QMimeType>
namespace {
bool databasePresentAtStartup=false;
void recordMimeDatabaseAtStartup()
{
    databasePresentAtStartup=QFile::exists(":/qt-project.org/qmime/packages/freedesktop.org.xml");
}
}
Q_COREAPP_STARTUP_FUNCTION(recordMimeDatabaseAtStartup)
class KisBrushQuayMimeResourceTest : public QObject {
    Q_OBJECT
private Q_SLOTS:
    void applicationDatabaseIsPresentBeforeFirstQuery()
    {
        QVERIFY2(databasePresentAtStartup,"The GUI test omitted the application's MIME resource before startup.");
        QMimeDatabase database;
        for (const auto &mime:QStringList{"image/png","image/jpeg"}) {
            const auto type=database.mimeTypeForName(mime);QVERIFY(type.isValid());QCOMPARE(type.name(),mime);
            QVERIFY(type.suffixes().contains(mime=="image/png"?"png":"jpg"));
        }
        QCOMPARE(database.mimeTypeForFile("generated.png",QMimeDatabase::MatchExtension).name(),QString("image/png"));
        QCOMPARE(database.mimeTypeForFile("generated.jpg",QMimeDatabase::MatchExtension).name(),QString("image/jpeg"));
    }
};
QTEST_GUILESS_MAIN(KisBrushQuayMimeResourceTest)
#include "KisBrushQuayMimeResourceTest.moc"

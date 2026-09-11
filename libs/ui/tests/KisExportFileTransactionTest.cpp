/* SPDX-FileCopyrightText: 2026 Trieflow LLC
 * SPDX-License-Identifier: GPL-3.0-or-later */
#include <QtTest>
#include <QFile>
#include <QTemporaryDir>
#include <filesystem>
#include "KisExportFileTransaction.h"

class KisExportFileTransactionTest : public QObject {
    Q_OBJECT
    static QString realDir(const QTemporaryDir &dir) { return QFileInfo(dir.path()).canonicalFilePath(); }
    static void write(const QString &p, const QByteArray &b) { QFile f(p); QVERIFY(f.open(QIODevice::WriteOnly)); QCOMPARE(f.write(b), b.size()); }
    static QByteArray bytes(const QString &p) { QFile f(p); if (!f.open(QIODevice::ReadOnly)) return {}; return f.readAll(); }
private Q_SLOTS:
    void newUnicodeOutputPublishes()
    {
        QTemporaryDir dir; const QString path=realDir(dir)+"/水彩.png";
        auto chosen=KisExportDestination::capture(path);
        KisExportFileTransaction job(chosen, {}); write(job.stagedPath(), "rendered PNG bytes");
        auto result=job.finish(true); QVERIFY(result.published); QVERIFY(result.error.isEmpty());
        QCOMPARE(bytes(path), QByteArray("rendered PNG bytes"));
    }
    void lateDestinationIsNeverOverwritten()
    {
        QTemporaryDir dir; const QString path=realDir(dir)+"/new.png";
        auto chosen=KisExportDestination::capture(path);
        KisExportFileTransaction job(chosen, {}); write(job.stagedPath(), "rendered"); write(path,"late owner");
        auto result=job.finish(true); QVERIFY(!result.published); QVERIFY(!result.error.isEmpty());
        QCOMPARE(bytes(path), QByteArray("late owner")); QCOMPARE(bytes(result.stagedPath), QByteArray("rendered"));
    }
    void confirmedReplacementRetainsOriginal()
    {
        QTemporaryDir dir; const QString path=realDir(dir)+"/old.png"; write(path,"original");
        auto chosen=KisExportDestination::capture(path); chosen.overwriteConfirmed=true;
        KisExportFileTransaction job(chosen, {}); write(job.stagedPath(), "new image");
        auto result=job.finish(true); QVERIFY(result.published); QCOMPARE(bytes(path), QByteArray("new image"));
        QCOMPARE(bytes(result.previousPath), QByteArray("original"));
    }
    void unconfirmedReplacementCannotStart()
    {
        QTemporaryDir dir; const QString path=realDir(dir)+"/old.png"; write(path,"original");
        auto chosen=KisExportDestination::capture(path);
        QVERIFY_THROWS_EXCEPTION(std::runtime_error, KisExportFileTransaction(chosen, {}));
        QCOMPARE(bytes(path), QByteArray("original"));
    }
    void changedConfirmedContentIsRetained()
    {
        QTemporaryDir dir; const QString path=realDir(dir)+"/old.png"; write(path,"original");
        auto chosen=KisExportDestination::capture(path); chosen.overwriteConfirmed=true;
        KisExportFileTransaction job(chosen, {}); write(job.stagedPath(), "new image"); write(path,"modified");
        auto result=job.finish(true); QVERIFY(!result.published); QCOMPARE(bytes(path), QByteArray("modified"));
    }
    void sameBytesDifferentIdentityIsRetained()
    {
        QTemporaryDir dir; const QString path=realDir(dir)+"/old.png"; write(path,"original");
        auto chosen=KisExportDestination::capture(path); chosen.overwriteConfirmed=true;
        KisExportFileTransaction job(chosen, {}); write(job.stagedPath(), "new image");
        QVERIFY(QFile::rename(path,path+".moved")); write(path,"original");
        auto result=job.finish(true); QVERIFY(!result.published); QCOMPARE(bytes(path), QByteArray("original"));
    }
    void failedOrCancelledExportPreservesOriginal_data()
    {
        QTest::addColumn<bool>("succeeded"); QTest::newRow("failure")<<false; QTest::newRow("cancel")<<true;
    }
    void failedOrCancelledExportPreservesOriginal()
    {
        QFETCH(bool,succeeded); QTemporaryDir dir; const QString path=realDir(dir)+"/old.png"; write(path,"original");
        auto chosen=KisExportDestination::capture(path); chosen.overwriteConfirmed=true;
        KisExportFileTransaction job(chosen, {}); write(job.stagedPath(), "partial");
        auto result=job.finish(succeeded, [] { return true; }); QVERIFY(!result.published);
        QCOMPARE(bytes(path), QByteArray("original"));
    }
    void cancellationAfterMovingOldRestoresIt()
    {
        QTemporaryDir dir; const QString path=realDir(dir)+"/old.png"; write(path,"original");
        auto chosen=KisExportDestination::capture(path); chosen.overwriteConfirmed=true;
        KisExportFileTransaction job(chosen, {}); write(job.stagedPath(), "new image");
        auto result=job.finish(true, [&] { return !QFile::exists(path); });
        QVERIFY(!result.published); QCOMPARE(bytes(path), QByteArray("original"));
    }
    void collisionAfterMovingOldRetainsEveryFile()
    {
        QTemporaryDir dir; const QString path=realDir(dir)+"/old.png"; write(path,"original");
        auto chosen=KisExportDestination::capture(path); chosen.overwriteConfirmed=true;
        KisExportFileTransaction job(chosen, {}); write(job.stagedPath(), "new image");
        auto result=job.finish(true, [&] { if (!QFile::exists(path)) write(path,"late owner"); return false; });
        QVERIFY(!result.published); QCOMPARE(bytes(path), QByteArray("late owner"));
        QCOMPARE(bytes(result.previousPath), QByteArray("original")); QCOMPARE(bytes(result.stagedPath), QByteArray("new image"));
    }
    void targetChangedBetweenCheckAndMoveIsRestored()
    {
        QTemporaryDir dir; const QString path=realDir(dir)+"/old.png"; write(path,"original");
        auto chosen=KisExportDestination::capture(path); chosen.overwriteConfirmed=true;
        KisExportFileTransaction job(chosen, {}); write(job.stagedPath(), "new image");
        int calls=0;
        auto result=job.finish(true, [&] {
            if (++calls==2) { if (!QFile::rename(path,path+".other-process")) qFatal("fixture rename failed"); write(path,"foreign replacement"); }
            return false;
        });
        QVERIFY(!result.published); QCOMPARE(bytes(path),QByteArray("foreign replacement"));
        QCOMPARE(bytes(path+".other-process"),QByteArray("original"));
        QCOMPARE(bytes(result.stagedPath),QByteArray("new image"));
    }
    void renamedParentCannotRedirectExport()
    {
        QTemporaryDir dir; auto root=realDir(dir); QVERIFY(QDir().mkdir(root+"/parent"));
        auto chosen=KisExportDestination::capture(root+"/parent/new.png");
        KisExportFileTransaction job(chosen, {}); write(job.stagedPath(), "new image");
        QVERIFY(QDir().rename(root+"/parent",root+"/moved-parent")); QVERIFY(QDir().mkdir(root+"/parent"));
        auto result=job.finish(true); QVERIFY(!result.published); QVERIFY(!QFile::exists(root+"/parent/new.png"));
    }
    void sourceAndHardlinkCannotBeTargets()
    {
        QTemporaryDir dir; const QString source=realDir(dir)+"/source.kra"; write(source,"source");
        auto chosen=KisExportDestination::capture(source); chosen.overwriteConfirmed=true;
        QVERIFY_THROWS_EXCEPTION(std::runtime_error, KisExportFileTransaction(chosen, {source}));
        const QString target=realDir(dir)+"/alias.png";
        std::filesystem::create_hard_link(std::filesystem::path(source.toStdString()),std::filesystem::path(target.toStdString()));
        chosen=KisExportDestination::capture(target); chosen.overwriteConfirmed=true;
        QVERIFY_THROWS_EXCEPTION(std::runtime_error, KisExportFileTransaction(chosen, {source}));
        QCOMPARE(bytes(source),QByteArray("source"));
    }
    void parentSymlinkAndSourceBasenameRemainProtected()
    {
        QTemporaryDir dir; auto root=realDir(dir); QVERIFY(QDir().mkdir(root+"/real"));
        const QString source=root+"/real/source.png"; write(source,"source");
        const QString real=root+"/real", alias=root+"/alias";
        std::filesystem::create_directory_symlink(std::filesystem::path(real.toStdString()),std::filesystem::path(alias.toStdString()));
        auto chosen=KisExportDestination::capture(root+"/alias/source.png"); chosen.overwriteConfirmed=true;
        QVERIFY_THROWS_EXCEPTION(std::runtime_error, KisExportFileTransaction(chosen, {source}));
        QCOMPARE(bytes(source),QByteArray("source"));
    }
    void protectedSourceChangePreventsPublication()
    {
        QTemporaryDir dir; auto root=realDir(dir); const QString source=root+"/source.kra"; write(source,"source");
        KisExportFileTransaction job(KisExportDestination::capture(root+"/new.png"), {source});
        write(job.stagedPath(), "new image"); write(source,"new source version");
        auto result=job.finish(true); QVERIFY(!result.published); QVERIFY(!QFile::exists(root+"/new.png"));
        QCOMPARE(bytes(source),QByteArray("new source version"));
    }
    void emptyRenderAndSecondFinishAreRejected()
    {
        QTemporaryDir dir; const QString path=realDir(dir)+"/new.png";
        KisExportFileTransaction job(KisExportDestination::capture(path), {}); write(job.stagedPath(), "");
        QVERIFY(!job.finish(true).published); write(job.stagedPath(), "late bytes");
        QVERIFY(!job.finish(true).published); QVERIFY(!QFile::exists(path));
    }
};
QTEST_GUILESS_MAIN(KisExportFileTransactionTest)
#include "KisExportFileTransactionTest.moc"

/* SPDX-FileCopyrightText: 2026 Trieflow LLC
 * SPDX-License-Identifier: GPL-3.0-or-later */
#include <QtTest>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTemporaryDir>
#include <QLockFile>
#include "KisExportPreset.h"
#include "KisExportPresetStore.h"

class KisExportPresetStoreTest : public QObject
{
    Q_OBJECT
    static KisExportPreset png()
    {
        KisExportPreset p;
        p.id = QUuid::createUuid();
        p.name = QString::fromUtf8("Illustration — 水彩");
        p.mimeType = "image/png";
        p.extension = "png";
        p.properties = {{"alpha", true}, {"compression", 7}, {"interlaced", false}};
        return p;
    }
    static QByteArray bytes(const QString &path)
    {
        QFile f(path); if (!f.open(QIODevice::ReadOnly)) return {};
        return f.readAll();
    }
    static void write(const QString &path, const QByteArray &data)
    {
        QFile f(path); QVERIFY(f.open(QIODevice::WriteOnly));
        QCOMPARE(f.write(data), data.size());
    }
private Q_SLOTS:
    void unicodeAndTypeRoundTrip()
    {
        QTemporaryDir dir; const auto path = dir.filePath("presets.json");
        KisExportPresetStore first(path); QVERIFY(first.load().ok());
        auto p = png(); QVERIFY(first.save(p).ok());
        KisExportPresetStore second(path); QVERIFY(second.load().ok());
        auto restored = second.find(p.id); QVERIFY(restored.has_value());
        QCOMPARE(restored->name, p.name);
        QCOMPARE(restored->properties, p.properties);
        QCOMPARE(restored->properties["compression"].userType(), int(QMetaType::Int));
        QCOMPARE(restored->properties["alpha"].userType(), int(QMetaType::Bool));
    }
    void deterministicSerialization()
    {
        auto p = png(); QByteArray a, b;
        QVERIFY(p.serialize(a).ok()); QVERIFY(p.serialize(b).ok()); QCOMPARE(a,b);
        KisExportPreset copy; QVERIFY(KisExportPreset::deserialize(a, copy).ok());
        QVERIFY(copy.serialize(b).ok()); QCOMPARE(a,b);
    }
    void jpegOptionsRemainTyped()
    {
        auto p = png(); p.mimeType = "image/jpeg"; p.extension = "jpg";
        p.properties = {{"quality", 91}, {"smoothing", 2}, {"progressive", true}, {"filters", ""}};
        QByteArray data; QVERIFY(p.serialize(data).ok()); KisExportPreset copy;
        QVERIFY(KisExportPreset::deserialize(data, copy).ok()); QCOMPARE(copy.properties, p.properties);
    }
    void updateAndDelete()
    {
        QTemporaryDir dir; KisExportPresetStore store(dir.filePath("presets.json"));
        QVERIFY(store.load().ok()); auto p = png(); QVERIFY(store.save(p).ok());
        p.name = "Updated"; QVERIFY(store.save(p).ok()); QCOMPARE(store.presets().size(), 1);
        QCOMPARE(store.find(p.id)->name, p.name); QVERIFY(store.remove(p.id).ok());
        QVERIFY(store.load().ok()); QVERIFY(store.presets().isEmpty());
    }
    void failedLoadBlocksAllMutation()
    {
        QTemporaryDir dir; const auto path = dir.filePath("presets.json");
        const QByteArray original("{malformed\nrecover this"); write(path, original);
        KisExportPresetStore store(path); auto error = store.load(); QVERIFY(!error.ok());
        QVERIFY(!error.recoveryPath.isEmpty()); QCOMPARE(bytes(error.recoveryPath), original);
        QVERIFY(!store.save(png()).ok()); QVERIFY(!store.remove(QUuid::createUuid()).ok());
        QCOMPARE(bytes(path), original);
    }
    void futureSchemaIsPreserved()
    {
        QTemporaryDir dir; const auto path = dir.filePath("presets.json");
        const QByteArray original("{\"schema\":999,\"presets\":[]}"); write(path, original);
        KisExportPresetStore store(path); auto error = store.load();
        QCOMPARE(error.code, KisExportPresetError::UnsupportedSchema);
        QVERIFY(!store.save(png()).ok()); QCOMPARE(bytes(path), original);
    }
    void writeRequiresLoad()
    {
        QTemporaryDir dir; KisExportPresetStore store(dir.filePath("presets.json"));
        QVERIFY(!store.save(png()).ok()); QVERIFY(!store.remove(QUuid::createUuid()).ok());
        QVERIFY(!QFile::exists(dir.filePath("presets.json")));
    }
    void canceledWritePreservesBytesAndMemory()
    {
        QTemporaryDir dir; const auto path = dir.filePath("presets.json");
        KisExportPresetStore store(path); QVERIFY(store.load().ok()); auto p = png();
        QVERIFY(store.save(p).ok()); const auto before = bytes(path); p.name = "Cancelled";
        QVERIFY(!store.save(p, [] { return true; }).ok()); QCOMPARE(bytes(path), before);
        QVERIFY(store.find(p.id)->name != p.name);
    }
    void cancelAfterStagingPreservesBytes()
    {
        QTemporaryDir dir; const auto path = dir.filePath("presets.json");
        KisExportPresetStore store(path); QVERIFY(store.load().ok()); auto p=png();
        QVERIFY(store.save(p).ok()); auto before=bytes(path); p.name="Cancelled later";
        int checks=0; QVERIFY(!store.save(p, [&] { return ++checks == 2; }).ok());
        QCOMPARE(checks, 2); QCOMPARE(bytes(path), before); QVERIFY(store.find(p.id)->name != p.name);
    }
    void externalChangeDuringStagingIsPreserved()
    {
        QTemporaryDir dir; const auto path = dir.filePath("presets.json");
        KisExportPresetStore store(path); QVERIFY(store.load().ok()); auto p=png();
        QVERIFY(store.save(p).ok()); const QByteArray foreign("other process data");
        int checks=0;
        auto result=store.save(p, [&] { if (++checks == 2) write(path, foreign); return false; });
        QCOMPARE(result.code, KisExportPresetError::Conflict); QCOMPARE(bytes(path), foreign);
        QVERIFY(!store.remove(p.id).ok()); QCOMPARE(bytes(path), foreign);
    }
    void anotherWriterCannotLoseUpdates()
    {
        QTemporaryDir dir; const auto path = dir.filePath("presets.json");
        KisExportPresetStore one(path), two(path); QVERIFY(one.load().ok()); QVERIFY(two.load().ok());
        auto p = png(); QVERIFY(one.save(p).ok()); const auto before = bytes(path);
        QVERIFY(!two.save(png()).ok()); QCOMPARE(bytes(path), before);
        QVERIFY(two.load().ok()); QVERIFY(two.save(png()).ok()); QCOMPARE(two.presets().size(), 2);
    }
    void busyLockLeavesOriginal()
    {
        QTemporaryDir dir; const auto path = dir.filePath("presets.json");
        KisExportPresetStore store(path); QVERIFY(store.load().ok()); auto p = png();
        QVERIFY(store.save(p).ok()); const auto before = bytes(path);
        QLockFile lock(path + ".lock"); QVERIFY(lock.tryLock());
        QVERIFY(!store.save(png()).ok()); QCOMPARE(bytes(path), before);
    }
    void invalidData_data()
    {
        QTest::addColumn<QString>("field"); QTest::addColumn<QVariant>("value");
        QTest::newRow("blank name") << "name" << QVariant("  ");
        QTest::newRow("null id") << "id" << QVariant(QUuid());
        QTest::newRow("path extension") << "extension" << QVariant("../png");
        QTest::newRow("wrong extension") << "extension" << QVariant("jpg");
        QTest::newRow("native mime") << "mime" << QVariant("application/x-krita");
        QTest::newRow("executable mime") << "mime" << QVariant("application/x-executable");
        QTest::newRow("path property") << "properties" << QVariant(QVariantMap{{"filename", "/home/private.kra"}});
        QTest::newRow("unknown object") << "properties" << QVariant(QVariantMap{{"alpha", QUrl("https://example.com")}});
        QTest::newRow("pixel bytes") << "properties" << QVariant(QVariantMap{{"alpha", QByteArray("pixels")}});
        QTest::newRow("wrong bool") << "properties" << QVariant(QVariantMap{{"alpha", "true"}});
        QTest::newRow("invalid range") << "properties" << QVariant(QVariantMap{{"compression", 99}});
    }
    void invalidData()
    {
        QFETCH(QString, field); QFETCH(QVariant, value); auto p=png();
        if(field=="name") p.name=value.toString();
        if(field=="id") p.id=value.toUuid();
        if(field=="extension") p.extension=value.toString();
        if(field=="mime") p.mimeType=value.toString();
        if(field=="properties") p.properties=value.toMap();
        QByteArray output("unchanged"); QVERIFY(!p.serialize(output).ok()); QCOMPARE(output, QByteArray("unchanged"));
    }
    void localColorDefinitionRoundTrip()
    {
        auto p = png();
        const QString xml = "<color channeldepth=\"U8\"><RGB r=\"1\" g=\"0.5\" b=\"0\" space=\"sRGB-elle-V2-srgbtrc.icc\"/></color>";
        p.properties.insert("transparencyFillcolor", xml);
        QByteArray bytes; QVERIFY(p.serialize(bytes).ok()); KisExportPreset copy;
        QVERIFY(KisExportPreset::deserialize(bytes, copy).ok());
        QCOMPARE(copy.properties["transparencyFillcolor"], QVariant(xml));
    }
    void unsafeColorXml_data()
    {
        QTest::addColumn<QString>("xml");
        QTest::newRow("entity") << "<!DOCTYPE color [<!ENTITY x SYSTEM 'file:///private'>]><color>&x;</color>";
        QTest::newRow("empty") << "<color/>";
        QTest::newRow("wrong root") << "<RGB r=\"1\"/>";
        QTest::newRow("path profile") << "<color><RGB space=\"C:/private.icc\"/></color>";
        QTest::newRow("metadata") << "<color><RGB/><metadata name=\"source\" value=\"/private\"/></color>";
        QTest::newRow("nested") << "<color><color><RGB/></color></color>";
        QTest::newRow("invalid channel") << "<color channeldepth=\"U8\"><RGB r=\"NaN\" g=\"0\" b=\"0\"/></color>";
    }
    void unsafeColorXml()
    {
        QFETCH(QString, xml); auto p=png(); p.properties.insert("transparencyFillcolor", xml);
        QByteArray bytes; QVERIFY(!p.serialize(bytes).ok());
    }
    void malformedPresetNeverMutatesResult()
    {
        auto p=png(); auto id=p.id;
        QVERIFY(!KisExportPreset::deserialize("{}",p).ok()); QCOMPARE(p.id,id);
    }
};
QTEST_GUILESS_MAIN(KisExportPresetStoreTest)
#include "KisExportPresetStoreTest.moc"

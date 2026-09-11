/* SPDX-FileCopyrightText: 2026 Trieflow LLC
 * SPDX-License-Identifier: GPL-2.0-or-later */
#include <QtTest>
#include <QClipboard>
#include <QMimeData>
#include <QImage>
#include <QUrl>
#include <testui.h>
#include <kis_clipboard.h>

class KisClipboardNullTest : public QObject {
    Q_OBJECT
private Q_SLOTS:
    void emptyClipboardQueriesAreSafe()
    {
        auto *system = QApplication::clipboard();
        system->clear();
        qInfo() << "Cleared native clipboard has null MIME data:" << (system->mimeData() == nullptr);
        auto *clipboard = KisClipboard::instance();
        QVERIFY(!clipboard->hasClip());
        QVERIFY(!clipboard->hasImage());
        QVERIFY(!clipboard->hasLayers());
        QVERIFY(!clipboard->hasLayerStyles());
        QVERIFY(!clipboard->hasUrls());
        QVERIFY(clipboard->layersMimeData() == nullptr);
        QVERIFY(clipboard->clipSize().isEmpty());
        QVERIFY(clipboard->getImageWithFallback(nullptr, false).isNull());
    }
    void populatedClipboardAndSubsequentClearKeepTheirMeaning()
    {
        auto *clipboard = KisClipboard::instance();
        auto *data = new QMimeData;
        QImage image(7, 5, QImage::Format_ARGB32); image.fill(Qt::blue);
        data->setImageData(image);
        data->setUrls({QUrl("https://example.invalid/clipboard-fixture")});
        data->setData("application/x-krita-node-internal-pointer", "fixture");
        data->setData("application/x-krita-layer-style", "fixture");
        QApplication::clipboard()->setMimeData(data);
        QVERIFY(clipboard->hasClip());
        QVERIFY(clipboard->hasImage());
        QVERIFY(clipboard->hasLayers());
        QVERIFY(clipboard->hasLayerStyles());
        QVERIFY(clipboard->hasUrls());
        QCOMPARE(clipboard->layersMimeData(), data);
        QCOMPARE(clipboard->clipSize(), QSize(7, 5));
        QApplication::clipboard()->clear();
        QVERIFY(!clipboard->hasClip());
        QVERIFY(!clipboard->hasImage());
        QVERIFY(!clipboard->hasLayers());
        QVERIFY(!clipboard->hasLayerStyles());
        QVERIFY(!clipboard->hasUrls());
        QVERIFY(clipboard->layersMimeData() == nullptr);
    }
};
KISTEST_MAIN(KisClipboardNullTest)
#include "KisClipboardNullTest.moc"

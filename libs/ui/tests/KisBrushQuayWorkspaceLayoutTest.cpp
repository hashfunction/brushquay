/* SPDX-FileCopyrightText: 2026 Trieflow LLC
 * SPDX-License-Identifier: GPL-3.0-or-later */
#include <QtTest>
#include <QApplication>
#include "KisBrushQuayWorkspaceLayouts.h"

class KisBrushQuayWorkspaceLayoutTest : public QObject {
    Q_OBJECT
    static void addDockers(QMainWindow &window)
    {
        auto ids=KisBrushQuayWorkspaceLayouts::dockerIds();
        ids << "UnselectedFixtureDocker";
        for (const auto &id:ids) {
            auto *dock=new QDockWidget(id,&window);dock->setObjectName(id);
            dock->setWidget(new QWidget);window.addDockWidget(Qt::LeftDockWidgetArea,dock);dock->show();
        }
    }
private Q_SLOTS:
    void hiddenDockersSurviveNativeStateRoundTrip_data()
    {
        QTest::addColumn<int>("layout");
        QTest::newRow("Illustration")<<0;QTest::newRow("Inking")<<1;
    }
    void hiddenDockersSurviveNativeStateRoundTrip()
    {
        QFETCH(int,layout);
        const auto kind=static_cast<KisBrushQuayWorkspaceLayouts::Kind>(layout);
        QMainWindow original;addDockers(original);QString error;
        QVERIFY2(KisBrushQuayWorkspaceLayouts::arrange(original,kind,error),qPrintable(error));
        const QStringList inactive=layout==0?QStringList{"sharedtooldocker","UnselectedFixtureDocker"}:
            QStringList{"ColorSelectorNg","History","OverviewDocker","UnselectedFixtureDocker"};
        for (const auto &id:inactive) {
            auto *dock=original.findChild<QDockWidget *>(id);QVERIFY(dock->isHidden());
        }
        const auto state=original.saveState();QVERIFY(!state.isEmpty());
        // Restore into a different initial topology with every docker visible,
        // matching workspace switching rather than reusing a layout's widgets.
        QMainWindow restored;addDockers(restored);
        for (int pass=0;pass<3;++pass) {
            for (auto *dock:restored.findChildren<QDockWidget *>()) dock->hide();
            QVERIFY(restored.restoreState(state));
            for (const auto &id:inactive) {
                auto *dock=restored.findChild<QDockWidget *>(id);
                QVERIFY2(dock->isHidden(),qPrintable("Inactive docker became visible after native restore: "+id));
            }
            for (const auto &id:QStringList{"ToolBox","KisLayerBox","PresetDocker"}) {
                auto *dock=restored.findChild<QDockWidget *>(id);QVERIFY(!dock->isHidden());
                QCOMPARE(restored.dockWidgetArea(dock),id=="ToolBox"?Qt::LeftDockWidgetArea:Qt::RightDockWidgetArea);
            }
        }
    }
    void missingRequiredDockerPreservesState()
    {
        QMainWindow window;addDockers(window);delete window.findChild<QDockWidget *>("KisLayerBox");
        const auto state=window.saveState();const auto size=window.size();QString error;
        QVERIFY(!KisBrushQuayWorkspaceLayouts::arrange(window,KisBrushQuayWorkspaceLayouts::Kind::Inking,error));
        QVERIFY(!error.isEmpty());QCOMPARE(window.saveState(),state);QCOMPARE(window.size(),size);
    }
};
QTEST_MAIN(KisBrushQuayWorkspaceLayoutTest)
#include "KisBrushQuayWorkspaceLayoutTest.moc"

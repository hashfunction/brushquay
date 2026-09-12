/* SPDX-FileCopyrightText: 2026 Trieflow LLC
 * SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef KIS_BRUSHQUAY_WORKSPACE_LAYOUTS_H
#define KIS_BRUSHQUAY_WORKSPACE_LAYOUTS_H
#include <QCoreApplication>
#include <QDockWidget>
#include <QLayout>
#include <QMainWindow>
#include <QMap>
#include <QToolBar>

/** Original layout recipes. Generate the installed .kws files on the accepted
 * Windows build through KisWorkspaceResource; these recipes contain no art,
 * external resources, user paths or document state. */
namespace KisBrushQuayWorkspaceLayouts {
enum class Kind { Illustration, Inking };
inline QString name(Kind kind)
{
    return kind==Kind::Illustration?QStringLiteral("BrushQuay Illustration"):QStringLiteral("BrushQuay Inking");
}
inline QStringList dockerIds()
{
    return {"ToolBox","KisLayerBox","PresetDocker","ColorSelectorNg","sharedtooldocker","History","OverviewDocker"};
}
inline bool arrange(QMainWindow &window,Kind kind,QString &error)
{
    if (kind!=Kind::Illustration && kind!=Kind::Inking) { error="Unknown BrushQuay workspace";return false; }
    QMap<QString,QDockWidget *> docks;
    const auto all=window.findChildren<QDockWidget *>(QString(),Qt::FindDirectChildrenOnly);
    for (const auto &id:dockerIds()) {
        for (auto *dock:all) if (dock->objectName()==id) docks.insert(id,dock);
        if (!docks.contains(id)) { error="Required native docker is unavailable: "+id;return false; }
    }
    // Validate every required docker before making any layout change.
    window.setDockNestingEnabled(true);window.setAnimated(false);window.resize(1440,900);window.move(0,0);
    for (auto *dock:all) { dock->setFloating(false);window.removeDockWidget(dock);dock->hide(); }
    for (auto *toolbar:window.findChildren<QToolBar *>(QString(),Qt::FindDirectChildrenOnly)) {
        const bool visible=QStringList{"mainToolBar","editToolBar","BrushesAndStuff"}.contains(toolbar->objectName());
        if (visible) window.addToolBar(Qt::TopToolBarArea,toolbar);
        toolbar->setVisible(visible);
    }
    auto *toolbox=docks["ToolBox"];auto *layers=docks["KisLayerBox"];auto *presets=docks["PresetDocker"];
    window.addDockWidget(Qt::LeftDockWidgetArea,toolbox);toolbox->show();
    window.addDockWidget(Qt::RightDockWidgetArea,layers);layers->show();
    if (kind==Kind::Illustration) {
        auto *color=docks["ColorSelectorNg"];auto *overview=docks["OverviewDocker"];auto *history=docks["History"];
        window.addDockWidget(Qt::RightDockWidgetArea,color);window.splitDockWidget(color,layers,Qt::Vertical);
        window.addDockWidget(Qt::RightDockWidgetArea,presets);window.splitDockWidget(layers,presets,Qt::Vertical);
        window.addDockWidget(Qt::RightDockWidgetArea,overview);window.tabifyDockWidget(color,overview);
        window.addDockWidget(Qt::RightDockWidgetArea,history);window.tabifyDockWidget(presets,history);
        color->show();overview->show();presets->show();history->show();color->raise();presets->raise();
        window.resizeDocks({color,layers,presets},{240,330,240},Qt::Vertical);
    } else {
        auto *options=docks["sharedtooldocker"];
        window.addDockWidget(Qt::RightDockWidgetArea,presets);window.splitDockWidget(layers,presets,Qt::Vertical);
        window.addDockWidget(Qt::RightDockWidgetArea,options);window.tabifyDockWidget(layers,options);
        presets->show();options->show();layers->raise();
        window.resizeDocks({layers,presets},{440,290},Qt::Vertical);
    }
    window.resizeDocks({toolbox},{48},Qt::Horizontal);
    window.resizeDocks({layers},{280},Qt::Horizontal);
    // Removed dockers are absent from QMainWindow's saved state. Restore then
    // reintroduces them with the destination window's old visibility. Keep
    // inactive dockers attached so the workspace records their hidden state.
    for (auto *dock:all) {
        if (window.dockWidgetArea(dock)==Qt::NoDockWidgetArea) {
            window.addDockWidget(Qt::RightDockWidgetArea,dock);dock->hide();
        }
    }
    if (window.layout()) window.layout()->activate();
    QCoreApplication::sendPostedEvents(nullptr,QEvent::LayoutRequest);
    error.clear();return true;
}
}
#endif

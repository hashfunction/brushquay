/* SPDX-FileCopyrightText: 2026 Trieflow LLC
 * SPDX-License-Identifier: GPL-3.0-or-later */
#include "KisExportPresetCodec.h"
#include "KisImportExportManager.h"
#include <KisMimeDatabase.h>
#include <KoColor.h>
#include <KoColorSpace.h>
#include <KoColorProfile.h>
#include <KoColorSpaceRegistry.h>
#include <kis_properties_configuration.h>
#include <QDomDocument>
#include <QScopedPointer>
namespace {
KisExportPresetResult invalid(const QString &message) { return {KisExportPresetError::InvalidPreset,message,{}}; }
}
KisExportPresetResult KisExportPresetCodec::capture(const QUuid &id,const QString &name,const QString &mime,const QString &extension,const KisPropertiesConfigurationSP &configuration,KisExportPreset &output)
{
    if (!configuration) return invalid("The format supplied no export settings.");
    KisExportPreset p; p.id=id; p.name=name; p.mimeType=mime; p.extension=extension;
    const auto properties=configuration->getProperties();
    for (auto it=properties.cbegin();it!=properties.cend();++it) {
        if (it.key()=="transparencyFillcolor" && it.value().userType()==qMetaTypeId<KoColor>()) {
            const auto color=it.value().value<KoColor>();
            QDomDocument doc; auto root=doc.createElement("color"); doc.appendChild(root);
            root.setAttribute("channeldepth",color.colorSpace()->colorDepthId().id());
            root.setAttribute("opacity",QString::number(color.opacityF(),'g',17));
            // Serialize the color space channels only; arbitrary KoColor metadata is not a setting.
            color.colorSpace()->colorToXML(color.data(),doc,root);
            p.properties.insert(it.key(),doc.toString(-1));
        } else p.properties.insert(it.key(),it.value());
    }
    auto result=p.validate(); if (!result.ok()) return result;
    output=p; return {};
}
KisExportPresetResult KisExportPresetCodec::restore(const KisExportPreset &preset,KisPropertiesConfigurationSP &output)
{
    auto result=preset.validate(); if (!result.ok()) return result;
    if (!KisImportExportManager::supportedMimeTypes(KisImportExportManager::Export).contains(preset.mimeType) || !KisMimeDatabase::suffixesForMimeType(preset.mimeType).contains(preset.extension)) return invalid("This preset's export format or extension is unavailable.");
    QScopedPointer<KisImportExportFilter> filter(KisImportExportManager::filterForMimeType(preset.mimeType,KisImportExportManager::Export));
    if (!filter) return invalid("The required export plug-in is unavailable.");
    auto config=filter->defaultConfiguration(); if (!config) return invalid("The export plug-in did not provide settings.");
    for (auto it=preset.properties.cbegin();it!=preset.properties.cend();++it) {
        if (!config->hasProperty(it.key())) return invalid("The installed plug-in no longer accepts an option: "+it.key());
        if (it.key()=="transparencyFillcolor") {
            QDomDocument doc; if (!doc.setContent(it.value().toString())) return invalid("Invalid background color.");
            const auto root=doc.documentElement(); const auto colorElement=root.firstChildElement();
            const auto profile=colorElement.attribute("space");
            if (!profile.isEmpty() && !KoColorSpaceRegistry::instance()->profileByName(profile)) return invalid("The preset's background color profile is unavailable: "+profile);
            bool ok=false; auto color=KoColor::fromXML(colorElement,root.attribute("channeldepth"),&ok);
            if (!ok || color.colorSpace()->colorDepthId().id()!=root.attribute("channeldepth") || (!profile.isEmpty() && color.profile()->name()!=profile)) return invalid("The preset's background color space is unavailable.");
            color.setOpacity(root.attribute("opacity","1").toDouble());
            config->setProperty(it.key(),QVariant::fromValue(color));
        } else {
            if (config->getProperty(it.key()).userType()!=it.value().userType()) return invalid("The installed plug-in changed an option type: "+it.key());
            config->setProperty(it.key(),it.value());
        }
    }
    output=config; return {};
}

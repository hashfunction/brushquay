/* SPDX-FileCopyrightText: 2026 Trieflow LLC
 * SPDX-License-Identifier: GPL-3.0-or-later */
#include "KisExportPreset.h"
#include <QDomDocument>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
#include <QSet>
#include <cmath>

namespace {
KisExportPresetResult invalid(const QString &message)
{
    return {KisExportPresetError::InvalidPreset, message, {}};
}
bool keysAre(const QJsonObject &object, const QStringList &keys)
{
    const auto objectKeys = object.keys();
    return QSet<QString>(objectKeys.begin(), objectKeys.end()) == QSet<QString>(keys.begin(), keys.end());
}
bool safeColorXml(const QString &xml)
{
    // KoColor XML contains color channels/profile names, never external entities or paths.
    if (xml.size() > 16384 || xml.contains("<!") || xml.contains("<?")) return false;
    QDomDocument doc;
    if (!doc.setContent(xml)) return false;
    const auto root = doc.documentElement();
    const QSet<QString> depths = {"U8", "U16", "F16", "F32", "F64"};
    if (root.tagName() != "color" || root.attributes().size() != 1 || !depths.contains(root.attribute("channeldepth"))) return false;
    const auto color = root.firstChildElement();
    if (color.isNull() || !color.nextSiblingElement().isNull() || !color.firstChildElement().isNull() || !root.text().trimmed().isEmpty()) return false;
    const QMap<QString, QStringList> models = {
        {"RGB", {"r", "g", "b"}}, {"sRGB", {"r", "g", "b"}},
        {"CMYK", {"c", "m", "y", "k"}}, {"Lab", {"L", "a", "b"}},
        {"XYZ", {"x", "y", "z"}}, {"Gray", {"g"}}, {"YCbCr", {"Y", "Cb", "Cr"}}
    };
    if (!models.contains(color.tagName())) return false;
    const auto channels = models.value(color.tagName());
    for (const auto &channel : channels) {
        bool ok = false; const double value = color.attribute(channel).toDouble(&ok);
        if (!ok || !std::isfinite(value) || std::abs(value) > 1000000) return false;
    }
    auto attrs = color.attributes();
    for (int i = 0; i < attrs.size(); ++i) {
        const auto attr = attrs.item(i).toAttr();
        if (attr.name() == "space") {
            if (attr.value().size() > 512 || attr.value().contains('/') || attr.value().contains('\\') || attr.value().contains(':')) return false;
        } else if (!channels.contains(attr.name())) return false;
    }
    return true;
}
}
QStringList KisExportPreset::supportedMimeTypes() { return {"image/png", "image/jpeg"}; }
KisExportPresetResult KisExportPreset::validate() const
{
    if (id.isNull() || name.trimmed().isEmpty() || name.size() > 160 || name.contains(QChar::Null)) return invalid("A preset needs a UUID and a name of 1–160 characters.");
    if (!supportedMimeTypes().contains(mimeType)) return invalid("This format has no reviewed export preset adapter.");
    if ((mimeType == "image/png" && extension != "png") || (mimeType == "image/jpeg" && extension != "jpg" && extension != "jpeg")) return invalid("The filename extension does not match the preset format.");
    const QSet<QString> pngBools = {"alpha", "indexed", "interlaced", "saveSRGBProfile", "forceSRGB", "saveAsHDR", "storeMetaData", "storeAuthor", "downsample"};
    const QSet<QString> jpegBools = {"progressive", "forceSRGB", "saveProfile", "optimize", "baseline", "exif", "iptc", "xmp", "storeAuthor", "storeMetaData"};
    const auto &bools = mimeType == "image/png" ? pngBools : jpegBools;
    for (auto it = properties.cbegin(); it != properties.cend(); ++it) {
        const auto key = it.key(); const auto value = it.value();
        if (bools.contains(key)) {
            if (value.userType() != QMetaType::Bool) return invalid("Boolean option has the wrong type: " + key);
        } else if ((mimeType == "image/png" && key == "compression") || (mimeType == "image/jpeg" && (key == "quality" || key == "smoothing" || key == "subsampling"))) {
            const int max = key == "compression" ? 9 : key == "subsampling" ? 3 : 100;
            if (value.userType() != QMetaType::Int || value.toInt() < 0 || value.toInt() > max) return invalid("Integer option is out of range or has the wrong type: " + key);
        } else if (key == "transparencyFillcolor") {
            if (value.userType() != QMetaType::QString || !safeColorXml(value.toString())) return invalid("Background color is not a supported local color definition.");
        } else if (mimeType == "image/jpeg" && key == "filters") {
            if (value.userType() != QMetaType::QString || value.toString().size() > 1024 || !QRegularExpression("^[A-Za-z0-9_, -]*$").match(value.toString()).hasMatch()) return invalid("Metadata filter names are invalid.");
        } else return invalid("Unknown or unsafe export option: " + key);
    }
    return {};
}
KisExportPresetResult KisExportPreset::serialize(QByteArray &output) const
{
    auto result = validate(); if (!result.ok()) return result;
    QJsonObject options;
    for (auto it = properties.cbegin(); it != properties.cend(); ++it) {
        const QString type = it.value().userType() == QMetaType::Bool ? "bool" : it.value().userType() == QMetaType::Int ? "int" : "string";
        options.insert(it.key(), QJsonObject{{"type", type}, {"value", QJsonValue::fromVariant(it.value())}});
    }
    output = QJsonDocument(QJsonObject{{"schema", Schema}, {"id", id.toString(QUuid::WithoutBraces)}, {"name", name}, {"mimeType", mimeType}, {"extension", extension}, {"properties", options}}).toJson(QJsonDocument::Compact);
    return {};
}
KisExportPresetResult KisExportPreset::deserialize(const QByteArray &data, KisExportPreset &output)
{
    if (data.size() > 65536) return invalid("Preset is too large.");
    QJsonParseError error; auto doc = QJsonDocument::fromJson(data, &error);
    if (error.error != QJsonParseError::NoError || !doc.isObject()) return invalid("Preset is not a JSON object.");
    const auto object = doc.object();
    if (object.value("schema") != QJsonValue(Schema)) return {KisExportPresetError::UnsupportedSchema, "Unsupported export preset version.", {}};
    if (!keysAre(object, {"schema", "id", "name", "mimeType", "extension", "properties"}) || !object.value("properties").isObject()) return invalid("Preset fields are invalid.");
    KisExportPreset p;
    p.id = QUuid(object.value("id").toString()); p.name = object.value("name").toString();
    p.mimeType = object.value("mimeType").toString(); p.extension = object.value("extension").toString();
    const auto options = object.value("properties").toObject();
    for (auto it = options.begin(); it != options.end(); ++it) {
        if (!it.value().isObject()) return invalid("Option lacks a type.");
        const auto option = it.value().toObject(); const auto value = option.value("value"); const auto type = option.value("type").toString();
        if (!keysAre(option, {"type", "value"})) return invalid("Option fields are invalid.");
        if (type == "bool" && value.isBool()) p.properties.insert(it.key(), value.toBool());
        else if (type == "int" && value.isDouble() && value.toDouble() >= -2147483648.0 && value.toDouble() <= 2147483647.0 && std::floor(value.toDouble()) == value.toDouble()) p.properties.insert(it.key(), int(value.toDouble()));
        else if (type == "string" && value.isString()) p.properties.insert(it.key(), value.toString());
        else return invalid("Unknown or mismatched option type.");
    }
    auto result = p.validate(); if (!result.ok()) return result;
    output = p; return {};
}

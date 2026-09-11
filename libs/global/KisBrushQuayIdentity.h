/* SPDX-FileCopyrightText: 2026 Trieflow LLC
 * SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef KIS_BRUSHQUAY_IDENTITY_H
#define KIS_BRUSHQUAY_IDENTITY_H
#include <QCoreApplication>
namespace KisBrushQuayIdentity {
inline constexpr char ApplicationId[]="brushquay";
inline constexpr char DisplayName[]="BrushQuay";
inline constexpr char Version[]="1.0.0";
inline constexpr char Publisher[]="Trieflow LLC";
inline constexpr char ProductUrl[]="https://brushquay.trieflow.com";
inline constexpr char PrivacyUrl[]="https://brushquay.trieflow.com/privacy";
inline constexpr char SupportUrl[]="https://brushquay.trieflow.com/support";
inline void apply()
{
    QCoreApplication::setApplicationName(QString::fromLatin1(ApplicationId));
    QCoreApplication::setApplicationVersion(QString::fromLatin1(Version));
    QCoreApplication::setOrganizationDomain(QStringLiteral("trieflow.com"));
    // Preserve one product-specific data directory; the publisher is shown in About/package metadata.
    QCoreApplication::setOrganizationName(QString());
}
}
#endif

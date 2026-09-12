set (krita_BUNDLE_FILES
     README
     Krita_4_Default_Resources.bundle
     RGBA_brushes.bundle
)
# Preserve the original SeExpr examples in source, but omit their installation
# until the authors' unversioned CC-BY-SA grant has a verified version.

if (NOT ANDROID)
    set (krita_BUNDLE_FILES
         ${krita_BUNDLE_FILES}
         Krita_3_Default_Resources.bundle
         )
endif()

install( FILES
    ${krita_BUNDLE_FILES}
    DESTINATION  ${KDE_INSTALL_DATADIR}/krita/bundles)

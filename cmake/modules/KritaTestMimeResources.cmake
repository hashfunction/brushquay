# SPDX-FileCopyrightText: 2026 Trieflow LLC
# SPDX-License-Identifier: GPL-3.0-or-later

# The Qt 6 application supplies the MIME XML that the pinned Qt build omits.
# Executables linking kritaui do not inherit the application executable's qrc.
function(kis_test_add_mime_database target)
    if(QT_MAJOR_VERSION STREQUAL "6")
        target_sources(${target} PRIVATE
            "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/../../krita/data/mime-database/mime-database.qrc")
        set_target_properties(${target} PROPERTIES AUTORCC ON)
    endif()
endfunction()

# SPDX-FileCopyrightText: 2026 Trieflow LLC
# SPDX-License-Identifier: GPL-3.0-or-later
cmake_minimum_required(VERSION 3.22)
project(BrushQuayDomainTests LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_AUTOMOC ON)
find_package(Qt6 6.5 REQUIRED COMPONENTS Core Test Xml)
enable_testing()
set(UI ../../libs/ui)
add_executable(KisExportPresetStoreTest ${UI}/tests/KisExportPresetStoreTest.cpp
    ${UI}/KisExportPreset.cpp ${UI}/KisExportPresetStore.cpp)
target_include_directories(KisExportPresetStoreTest PRIVATE ${UI})
target_link_libraries(KisExportPresetStoreTest PRIVATE Qt6::Core Qt6::Test Qt6::Xml)
add_test(NAME KisExportPresetStoreTest COMMAND KisExportPresetStoreTest)
add_executable(KisExportFileTransactionTest ${UI}/tests/KisExportFileTransactionTest.cpp
    ${UI}/KisExportFileTransaction.cpp)
target_include_directories(KisExportFileTransactionTest PRIVATE ${UI})
target_link_libraries(KisExportFileTransactionTest PRIVATE Qt6::Core Qt6::Test)
add_test(NAME KisExportFileTransactionTest COMMAND KisExportFileTransactionTest)
add_executable(KisBrushQuayIdentityTest ${UI}/tests/KisBrushQuayIdentityTest.cpp
    ../../krita/pics/branding/BrushQuay/branding.qrc)
set_target_properties(KisBrushQuayIdentityTest PROPERTIES AUTORCC ON)
target_include_directories(KisBrushQuayIdentityTest PRIVATE ../../libs/global)
target_link_libraries(KisBrushQuayIdentityTest PRIVATE Qt6::Core Qt6::Test)
add_test(NAME KisBrushQuayIdentityTest COMMAND KisBrushQuayIdentityTest)

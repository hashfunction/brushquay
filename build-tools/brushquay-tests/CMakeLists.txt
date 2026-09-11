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

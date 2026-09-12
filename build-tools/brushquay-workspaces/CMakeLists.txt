# SPDX-FileCopyrightText: 2026 Trieflow LLC
# SPDX-License-Identifier: GPL-3.0-or-later
cmake_minimum_required(VERSION 3.22)
project(BristluneWorkspaceCompile LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
find_package(Qt6 6.5 REQUIRED COMPONENTS Core Widgets)
add_library(brushquay-workspace-layout-compile STATIC compile.cpp)
target_link_libraries(brushquay-workspace-layout-compile PRIVATE Qt6::Core Qt6::Widgets)
target_include_directories(brushquay-workspace-layout-compile PRIVATE ../../libs/ui)

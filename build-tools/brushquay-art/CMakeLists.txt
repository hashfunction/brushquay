# SPDX-FileCopyrightText: 2026 Trieflow LLC
# SPDX-License-Identifier: GPL-3.0-or-later
cmake_minimum_required(VERSION 3.22)
project(BristluneArtGenerator LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
find_package(Qt6 REQUIRED COMPONENTS Core Gui Svg)
add_executable(render-brushquay-svg render.cpp)
target_link_libraries(render-brushquay-svg PRIVATE Qt6::Core Qt6::Gui Qt6::Svg)

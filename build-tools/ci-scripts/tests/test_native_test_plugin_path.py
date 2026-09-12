"""Exercise the generated SDK configuration consumed before test application startup."""

from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]


class NativeTestPluginPathTests(unittest.TestCase):
    def test_build_tree_override_survives_generated_sdk_header(self):
        with tempfile.TemporaryDirectory(prefix="brushquay plugin path ") as directory:
            root = Path(directory)
            (root / "KoConfig.h").write_text("")
            (root / "probe.cpp").write_text(
                '#include "KoTestConfig.h"\n#include <cstdio>\n#include <cstring>\n'
                'int main(int argc, char **argv) { std::puts(KRITA_PLUGINS_DIR_FOR_TESTS); '
                'return argc != 2 || std::strcmp(KRITA_PLUGINS_DIR_FOR_TESTS, argv[1]) != 0; }\n'
            )
            template = (ROOT / "KoTestConfig.h.cmake").as_posix()
            (root / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.22)\n"
                "project(plugin_path_probe LANGUAGES CXX)\n"
                'set(CMAKE_INSTALL_PREFIX "${CMAKE_BINARY_DIR}/not installed")\n'
                'set(KDE_INSTALL_DATADIR "share")\n'
                'set(KRITA_PLUGIN_INSTALL_DIR "lib/kritaplugins")\n'
                'configure_file("' + template + '" "${CMAKE_BINARY_DIR}/KoTestConfig.h")\n'
                "foreach(target default_path build_path)\n"
                '  add_executable(${target} probe.cpp)\n'
                '  target_include_directories(${target} PRIVATE "${CMAKE_BINARY_DIR}" "${CMAKE_CURRENT_SOURCE_DIR}")\n'
                "endforeach()\n"
                'target_compile_definitions(build_path PRIVATE KRITA_PLUGINS_DIR_FOR_TESTS="$<TARGET_FILE_DIR:build_path>")\n'
                "enable_testing()\n"
                'add_test(NAME default_path COMMAND default_path "${CMAKE_INSTALL_PREFIX}/lib/kritaplugins")\n'
                'add_test(NAME build_path COMMAND build_path "$<TARGET_FILE_DIR:build_path>")\n'
            )

            def checked(arguments):
                result = subprocess.run(arguments, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return result

            build = root / "build"
            checked(["cmake", "-S", str(root), "-B", str(build)])
            checked(["cmake", "--build", str(build), "--config", "Release"])
            checked(["ctest", "--test-dir", str(build), "-C", "Release", "--output-on-failure"])


if __name__ == "__main__":
    unittest.main()

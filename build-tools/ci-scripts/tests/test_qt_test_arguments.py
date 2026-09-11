"""Exercise the production CMake test macro's real command registration."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


class QtTestArgumentsTests(unittest.TestCase):
    def test_report_arguments_reach_registered_commands_and_defaults_stay_empty(self):
        with tempfile.TemporaryDirectory(
            prefix="brushquay test arguments "
        ) as directory:
            root = Path(directory)
            modules = root / "modules"
            modules.mkdir()
            for module, function in (
                ("ECMMarkAsTest", "ecm_mark_as_test"),
                ("ECMMarkNonGuiExecutable", "ecm_mark_nongui_executable"),
                ("KritaTestSuite", "set_test_sdk_compile_definitions"),
            ):
                (modules / (module + ".cmake")).write_text(
                    "function(" + function + " target)\nendfunction()\n"
                )
            (root / "main.cpp").write_text(
                "#include <cstdio>\nint main(int argc,char**argv){for(int i=1;i<argc;++i)std::puts(argv[i]);return 0;}\n"
            )
            macro = (ROOT / "cmake/modules/KritaAddBrokenUnitTest.cmake").as_posix()
            (root / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.22)\nproject(argument_probe LANGUAGES CXX)\nenable_testing()\n"
                'list(PREPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/modules")\n'
                'include("' + macro + '")\n'
                "kis_add_test(main.cpp TEST_NAME original NAME_PREFIX probe-)\n"
                'kis_add_test(main.cpp TEST_NAME reports NAME_PREFIX probe- TEST_ARGUMENTS -o "report with spaces.xml,junitxml" -o "report.log,txt")\n'
            )
            build = root / "build"

            def checked(args):
                result = subprocess.run(args, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return result

            checked(["cmake", "-S", str(root), "-B", str(build)])
            checked(["cmake", "--build", str(build), "--config", "Release"])
            inventory = json.loads(
                checked(
                    [
                        "ctest",
                        "--test-dir",
                        str(build),
                        "-C",
                        "Release",
                        "--show-only=json-v1",
                    ]
                ).stdout
            )
            commands = {test["name"]: test["command"] for test in inventory["tests"]}
            self.assertEqual(len(commands["probe-original"]), 1)
            self.assertEqual(
                commands["probe-reports"][1:],
                ["-o", "report with spaces.xml,junitxml", "-o", "report.log,txt"],
            )
            output = checked(
                ["ctest", "--test-dir", str(build), "-C", "Release", "--verbose"]
            ).stdout
            self.assertIn("report with spaces.xml,junitxml", output)
            self.assertIn("report.log,txt", output)


if __name__ == "__main__":
    unittest.main()

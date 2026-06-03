with open("scripts/docmeta/tests/test_check_planning_registration.py", "r") as f:
    code = f.read()

import re

method_replacement = r'''    @patch("sys.stderr", new_callable=StringIO)
    def test_strict_exits_non_zero_when_findings_exist(self, mock_stderr):
        self.write_file("docs/blueprints/unregistered.md", "---\nstatus: active\n---\nBody")

        exit_code = check_plan.main([])
        self.assertEqual(exit_code, 0)

        exit_code = check_plan.main(["--mode", "warn"])
        self.assertEqual(exit_code, 0)

        exit_code = check_plan.main(["--strict"])
        self.assertEqual(exit_code, 1)

        exit_code = check_plan.main(["--mode", "strict"])
        self.assertEqual(exit_code, 1)
'''

pre, post = code.split('    @patch("sys.stderr", new_callable=StringIO)', 1)

with open("scripts/docmeta/tests/test_check_planning_registration.py", "w") as f:
    f.write(pre + method_replacement + '\nif __name__ == "__main__":\n    unittest.main()\n')

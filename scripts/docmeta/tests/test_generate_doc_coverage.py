import unittest

from scripts.docmeta.generate_doc_coverage import render


class RegisteredCoverageReportTests(unittest.TestCase):
    def test_report_does_not_claim_repository_wide_coverage(self):
        text = render()
        self.assertIn("Registered Implementation Documentation Coverage", text)
        self.assertIn("not repository-wide documentation coverage", text)
        self.assertIn("audit/impl-registry.yaml", text)


if __name__ == "__main__":
    unittest.main()

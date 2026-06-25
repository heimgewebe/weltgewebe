from __future__ import annotations

import unittest
from pathlib import Path

from scripts.agent.validate_agent_contracts import validate_contracts
from scripts.docmeta.docmeta import REPO_ROOT


class TestValidateAgentContracts(unittest.TestCase):
    def test_repository_contract_cases(self):
        self.assertEqual(validate_contracts(Path(REPO_ROOT)), [])


if __name__ == "__main__":
    unittest.main()

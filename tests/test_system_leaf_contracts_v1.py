from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from noetrium_platform.foundation.governance.system_registry.api import system_catalog


class SystemLeafContractTests(unittest.TestCase):
    def test_migrated_declaration_leaves_have_contract_and_runtime_owner(self) -> None:
        migrated = 0
        for descriptor in system_catalog():
            package = ROOT.joinpath(*descriptor.package_prefix.split("."))
            boundary = package / "api" / "boundary.py"
            if not boundary.is_file() or "SystemLeafContract" not in boundary.read_text(encoding="utf-8"):
                continue
            migrated += 1
            boundary_module = __import__(descriptor.package_prefix + ".api.boundary", fromlist=["contract"])
            owner_module = __import__(descriptor.package_prefix + ".runtime.owner", fromlist=["owner"])
            contract = boundary_module.contract()
            owner = owner_module.owner()
            self.assertIs(boundary_module.CONTRACT, contract)
            self.assertIs(owner_module.OWNER, owner)
            self.assertEqual(contract.node, descriptor.identity.key)
            self.assertEqual(contract.authority_id, descriptor.authority_id)
            self.assertEqual(owner.owner_id, descriptor.authority_id)
            self.assertEqual(contract.package_prefix, descriptor.package_prefix)
            self.assertEqual(len(contract.digest), 64)
            self.assertEqual(contract.api_module, descriptor.package_prefix + ".api")
            self.assertEqual(contract.runtime_module, descriptor.package_prefix + ".runtime")
            self.assertTrue((package / "api").is_dir())
            self.assertTrue((package / "runtime").is_dir())
            self.assertTrue((package / "providers").is_dir())
            self.assertTrue((package / "composition").is_dir())
        # Architecture convergence may delete generic shells; retained leaves must all conform.
        self.assertGreater(migrated, 0)


if __name__ == "__main__":
    unittest.main()

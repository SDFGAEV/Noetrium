from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from research_platform.reliability.forensics.providers.segmented_hashlog import SegmentedHashChainedJSONL
from research_platform.reliability.forensics.providers.hashlog import HashChainError
from research_platform.reliability.forensics.providers.directory_change_signal import DirectoryChangeSignal


class SegmentedEventHotPathV173Tests(unittest.TestCase):
    def test_steady_state_append_does_not_enumerate_all_segments(self) -> None:
        with TemporaryDirectory() as td:
            ledger = SegmentedHashChainedJSONL(
                Path(td) / "events",
                max_segment_bytes=128,
                fsync_every=4,
            )
            # First append initializes/verifies the writer state.
            ledger.append({"event": 0, "payload": "x" * 100})
            # Force multiple rotations so an O(segment-count) check would be visible.
            for value in range(1, 8):
                ledger.append({"event": value, "payload": "x" * 100})
            with patch.object(
                ledger,
                "_segment_files",
                side_effect=AssertionError("steady-state append enumerated segment directory"),
            ):
                ledger.append({"event": 9, "payload": "hot"})

    def test_external_segment_directory_change_still_fails_closed(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td) / "events"
            ledger = SegmentedHashChainedJSONL(root, fsync_every=4)
            ledger.append({"event": 1})
            (root / "99999999.jsonl").write_text("", encoding="utf-8")
            with self.assertRaises(Exception):
                ledger.append({"event": 2})

    @unittest.skipUnless(sys.platform == "win32", "Windows change-notification contract")
    def test_windows_fresh_directory_creation_signal_has_zero_misses(self) -> None:
        with TemporaryDirectory() as td:
            base = Path(td)
            for index in range(500):
                root = base / f"watch-{index}"
                root.mkdir()
                signal = DirectoryChangeSignal(root)
                self.assertEqual(signal.mode, "windows-notify")
                (root / "99999999.jsonl").write_bytes(b"")
                self.assertTrue(signal.changed_since(None))
                signal.close()


    @unittest.skipUnless(sys.platform == "win32", "Windows change-notification contract")
    def test_windows_change_signal_detects_repeated_create_delete_rename(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td) / "events"
            root.mkdir()
            signal = DirectoryChangeSignal(root)
            for index in range(100):
                path = root / f"entry-{index}.a"
                path.write_bytes(b"x")
                self.assertTrue(signal.changed_since(None)); signal.acknowledge()
                renamed = path.with_suffix(".b")
                path.rename(renamed)
                self.assertTrue(signal.changed_since(None)); signal.acknowledge()
                renamed.unlink()
                self.assertTrue(signal.changed_since(None)); signal.acknowledge()
            signal.close()


    def test_external_directory_mutation_during_active_append_fails_closed(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td) / "events"
            ledger = SegmentedHashChainedJSONL(root, fsync_every=4)
            ledger.append({"event": 1})
            original = ledger._writer.append
            def inject(payload):
                receipt = original(payload)
                (root / "99999999.jsonl").write_bytes(b"")
                return receipt
            ledger._writer.append = inject
            with self.assertRaisesRegex(HashChainError, "during owning writer append"):
                ledger.append({"event": 2})

    def test_owned_segment_creation_does_not_mask_extra_directory_entry(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td) / "events"
            ledger = SegmentedHashChainedJSONL(root, fsync_every=4)
            original = ledger._writer.append
            def inject(payload):
                receipt = original(payload)
                (root / "99999999.jsonl").write_bytes(b"")
                return receipt
            ledger._writer.append = inject
            with self.assertRaisesRegex(HashChainError, "namespace drift"):
                ledger.append({"event": 1})


if __name__ == "__main__":
    unittest.main()

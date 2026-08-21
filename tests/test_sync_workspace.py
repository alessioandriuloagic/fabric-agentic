import unittest

from scripts.branch_out import RailError
from scripts.sync_workspace import changed_item_names, is_aligned, validate_status


class SyncWorkspaceTests(unittest.TestCase):
    def test_aligned_status_requires_matching_heads_and_no_changes(self) -> None:
        self.assertTrue(is_aligned({"workspaceHead": "abc", "remoteCommitHash": "abc", "changes": []}))

    def test_remote_change_returns_item_name_without_divergence(self) -> None:
        status = {
            "workspaceHead": "abc",
            "remoteCommitHash": "def",
            "changes": [{"remoteChange": "Modified", "conflictType": "None", "itemMetadata": {"displayName": "nb_load"}}],
        }

        validate_status(status)
        self.assertEqual(changed_item_names(status), ["nb_load"])

    def test_conflict_or_workspace_change_fails_without_overwriting(self) -> None:
        with self.assertRaisesRegex(RailError, "conflict"):
            validate_status({"changes": [{"conflictType": "Conflict"}]})
        with self.assertRaisesRegex(RailError, "divergence"):
            validate_status({"changes": [{"workspaceChange": "Modified", "conflictType": "None"}]})


if __name__ == "__main__":
    unittest.main()
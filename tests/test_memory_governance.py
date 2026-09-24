import unittest
from datetime import datetime, timedelta, timezone

from app.memory_governance import GovernedMemoryStore, MAX_RETENTION_DAYS, MemoryOwner


class GovernedMemoryStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 9, 24, tzinfo=timezone.utc)
        self.owner = MemoryOwner("campus-a", "student-1")
        self.store = GovernedMemoryStore(clock=lambda: self.now)

    def test_blocks_pii_before_persistence(self) -> None:
        result = self.store.write(
            owner=self.owner,
            key="contact",
            value="student@example.test",
            purpose="聯絡",
            retention_days=30,
            approved=True,
        )

        self.assertFalse(result.decision.allowed)
        self.assertEqual(result.decision.rule, "pii_memory_write")
        self.assertEqual(self.store.query(self.owner), ())

    def test_caps_retention_and_purges_expired_records(self) -> None:
        result = self.store.write(
            owner=self.owner,
            key="response_tone",
            value="簡短回答",
            purpose="調整回答格式",
            retention_days=90,
            approved=True,
        )

        self.assertEqual(result.decision.rule, "memory_retention_capped")
        self.assertIsNotNone(result.record)
        assert result.record is not None
        self.assertEqual(
            result.record.expires_at,
            self.now + timedelta(days=MAX_RETENTION_DAYS),
        )
        self.assertEqual(self.store.purge_expired(result.record.expires_at), 1)
        self.assertEqual(self.store.query(self.owner), ())

    def test_denies_cross_user_read(self) -> None:
        result = self.store.write(
            owner=self.owner,
            key="response_tone",
            value="簡短回答",
            purpose="調整回答格式",
            retention_days=30,
            approved=True,
        )
        assert result.record is not None

        record, decision = self.store.read_record(
            requester=MemoryOwner("campus-a", "student-2"),
            record_id=result.record.record_id,
        )

        self.assertIsNone(record)
        self.assertEqual(decision.rule, "user_memory_isolation")

    def test_owner_can_query_and_delete_memory(self) -> None:
        result = self.store.write(
            owner=self.owner,
            key="response_tone",
            value="簡短回答",
            purpose="調整回答格式",
            retention_days=30,
            approved=True,
        )
        assert result.record is not None

        self.assertEqual(len(self.store.query(self.owner)), 1)
        decision = self.store.delete(
            requester=self.owner,
            record_id=result.record.record_id,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.rule, "user_memory_delete")
        self.assertEqual(self.store.query(self.owner), ())


if __name__ == "__main__":
    unittest.main()

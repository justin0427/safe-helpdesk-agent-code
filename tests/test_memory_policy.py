import unittest

from app.memory_policy import MemoryRecord, SessionMemoryStore


class SessionMemoryStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = SessionMemoryStore()

    def test_keeps_working_memory_inside_one_tenant_and_session(self) -> None:
        decision = self.store.write(
            MemoryRecord("campus-a", "session-1", "device", "Windows 11", "working")
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(len(self.store.read(tenant_id="campus-a", session_id="session-1")), 1)
        self.assertEqual(len(self.store.read(tenant_id="campus-b", session_id="session-1")), 0)

    def test_rejects_sensitive_memory(self) -> None:
        decision = self.store.write(
            MemoryRecord("campus-a", "session-1", "secret", "密碼：mock-secret", "working")
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.rule, "sensitive_memory_write")

    def test_rejects_a_mock_backup_code_without_a_label(self) -> None:
        decision = self.store.write(
            MemoryRecord("campus-a", "session-1", "secret", "MOCK-948201", "working")
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.rule, "sensitive_memory_write")

    def test_requires_approval_for_persistent_preference(self) -> None:
        decision = self.store.write(
            MemoryRecord("campus-a", "session-1", "tone", "簡短回答", "preference")
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.rule, "persistent_memory_requires_approval")

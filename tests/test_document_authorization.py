import unittest

from app.document_authorization import (
    Principal,
    SecuredDocument,
    filter_authorized_documents,
)


class DocumentAuthorizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.principal = Principal(
            user_id="student.demo",
            tenant_id="tenant-a",
            roles=frozenset({"helpdesk"}),
        )

    def test_filters_other_tenants_before_retrieval(self) -> None:
        document = SecuredDocument(
            article_id="SOP-B-001",
            tenant_id="tenant-b",
            allowed_roles=frozenset({"helpdesk"}),
            title="VPN",
            content="other tenant",
        )

        allowed, decisions = filter_authorized_documents(self.principal, [document])

        self.assertEqual(allowed, [])
        self.assertEqual(decisions[0].rule, "tenant_isolation")

    def test_filters_same_tenant_document_without_the_required_role(self) -> None:
        document = SecuredDocument(
            article_id="SOP-A-ADMIN",
            tenant_id="tenant-a",
            allowed_roles=frozenset({"admin"}),
            title="Admin",
            content="admin only",
        )

        allowed, decisions = filter_authorized_documents(self.principal, [document])

        self.assertEqual(allowed, [])
        self.assertEqual(decisions[0].rule, "document_acl")

    def test_allows_a_document_for_the_current_tenant_and_role(self) -> None:
        document = SecuredDocument(
            article_id="SOP-A-VPN",
            tenant_id="tenant-a",
            allowed_roles=frozenset({"helpdesk"}),
            title="VPN",
            content="restart client",
        )

        allowed, decisions = filter_authorized_documents(self.principal, [document])

        self.assertEqual(allowed, [document])
        self.assertEqual(decisions[0].rule, "document_authorized")

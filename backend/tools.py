"""The three recovery tools. Nothing here touches a payment rail, SMS, or email provider."""

from backend.audit import AuditLog
from backend.store import CustomerStore

PAYMENT_LINK_HOST = "https://pay.example.com/link"
ESCALATION_REASONS = {"customer_dispute", "amount_dispute", "customer_request"}


class ToolError(Exception):
    pass


class Tools:
    def __init__(self, store: CustomerStore, audit: AuditLog):
        self.store = store
        self.audit = audit

    def _customer(self, customer_id: str) -> dict:
        record = self.store.get(customer_id)
        if record is None:
            raise ToolError(f"unknown customer_id: {customer_id}")
        return record

    def check_payment_status(self, customer_id: str) -> dict:
        record = self._customer(customer_id)
        result = {
            "amount_due": record["amount_due"],
            "currency": record["currency"],
            "due_date": record["due_date"],
            "failure_reason": record["failure_reason"],
            "autopay_status": record["autopay_status"],
            "is_disputing": record["is_disputing"],
            "retry_count": record["retry_count"],
        }
        self.audit.record("check_payment_status", customer_id, result)
        return result

    def retry_autopay_charge(self, customer_id: str) -> dict:
        record = self._customer(customer_id)
        result = {
            "status": record["retry_result"],
        }
        self.audit.record("retry_autopay_charge", customer_id, result)
        return result

    def send_payment_link(self, customer_id: str) -> dict:
        self._customer(customer_id)
        result = {
            "status": "sent",
            "link": f"{PAYMENT_LINK_HOST}/{customer_id}",
        }
        self.audit.record("send_payment_link", customer_id, result)
        return result

    def escalate_to_human(self, customer_id: str, reason: str) -> dict:
        if reason not in ESCALATION_REASONS:
            raise ToolError(f"reason must be one of {sorted(ESCALATION_REASONS)}")
        self._customer(customer_id)
        result = {
            "status": "escalation_requested",
            "reason": reason,
            "message": "Request recorded for a human agent. No transfer was made.",
        }
        self.audit.record("escalate_to_human", customer_id, result, reason=reason)
        return result

import json

import pytest

from backend.audit import AuditLog
from backend.store import CustomerStore
from backend.tools import PAYMENT_LINK_HOST, Tools, ToolError


@pytest.fixture
def audit(tmp_path):
    return AuditLog(tmp_path / "audit.jsonl")


@pytest.fixture
def tools(audit):
    return Tools(CustomerStore(), audit)

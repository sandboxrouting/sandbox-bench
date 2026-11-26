from __future__ import annotations

import pytest

from sandbox_bench import providers
from sandbox_bench.adapter import AccountError, Spec
from sandbox_bench.providers._template import Acme


def test_template_is_skipped_but_valid() -> None:
    assert "_template" not in providers.available()
    assert providers.validate(Acme) == []
    assert all(Acme.implements(op) for op in providers.OPTIONAL_OPERATIONS)


def test_template_reads_its_key_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ACME_API_KEY", raising=False)
    with pytest.raises(AccountError, match="ACME_API_KEY"):
        Acme()
    monkeypatch.setenv("ACME_API_KEY", "k")
    acme = Acme()
    with pytest.raises(NotImplementedError):
        acme.create(Spec("sbx-t"))
    acme.close()

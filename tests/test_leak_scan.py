from __future__ import annotations

from pathlib import Path

from graph_harness_maintain.leak_scan import scan_public_surface


def test_local_identity_email_in_public_docs_is_blocking(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("contact VANILAAAAAAAA <xchen247@uw.edu>\n", encoding="utf-8")
    report = scan_public_surface(tmp_path)
    findings = [item for item in report["findings"] if item["path"] == "README.md"]
    assert report["status"] == "FAIL"
    assert report["blocking_count"] >= 1
    assert any(item["rule"] == "local_identity_email" for item in findings)


def test_local_identity_email_in_identity_guard_is_informational(tmp_path: Path) -> None:
    identity_path = tmp_path / "src" / "graph_harness_maintain" / "identity.py"
    identity_path.parent.mkdir(parents=True, exist_ok=True)
    identity_path.write_text('EXPECTED_EMAIL = "xchen247@uw.edu"\n', encoding="utf-8")
    report = scan_public_surface(tmp_path)
    findings = [item for item in report["findings"] if item["path"] == "src/graph_harness_maintain/identity.py"]
    assert findings
    assert all(item["classification"] == "informational" for item in findings)

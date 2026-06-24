from pathlib import Path

import importlib.util
import sys


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "privacy_scan.py"
spec = importlib.util.spec_from_file_location("privacy_scan", SCRIPT)
privacy_scan = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules["privacy_scan"] = privacy_scan
spec.loader.exec_module(privacy_scan)


def test_scan_blocks_absolute_user_path(tmp_path: Path) -> None:
    target = tmp_path / "README.md"
    target.write_text("path=/Users/example/private\n", encoding="utf-8")
    config = {
        "blocked_literals": ["/Users/"],
        "blocked_regex": [],
        "blocked_terms": [],
        "allowed_paths": [],
    }
    hits = privacy_scan.scan(tmp_path, config)
    assert len(hits) == 1
    assert hits[0].kind == "literal"


def test_scan_blocks_secret_regex(tmp_path: Path) -> None:
    target = tmp_path / "config.yaml"
    target.write_text("token = \"sk-abcdefghijklmnopqrstuvwxyz\"\n", encoding="utf-8")
    config = {
        "blocked_literals": [],
        "blocked_regex": [r"sk-[A-Za-z0-9_-]{20,}"],
        "blocked_terms": [],
        "allowed_paths": [],
    }
    hits = privacy_scan.scan(tmp_path, config)
    assert len(hits) == 1
    assert hits[0].kind == "regex"


def test_scan_allows_ignored_paths(tmp_path: Path) -> None:
    ignored = tmp_path / ".git" / "config"
    ignored.parent.mkdir()
    ignored.write_text("/Users/example/private\n", encoding="utf-8")
    config = {
        "blocked_literals": ["/Users/"],
        "blocked_regex": [],
        "blocked_terms": [],
        "allowed_paths": [".git/"],
    }
    hits = privacy_scan.scan(tmp_path, config)
    assert hits == []


def run_all() -> None:
    import tempfile

    tests = [
        test_scan_blocks_absolute_user_path,
        test_scan_blocks_secret_regex,
        test_scan_allows_ignored_paths,
    ]
    for test in tests:
        with tempfile.TemporaryDirectory() as tmp:
            test(Path(tmp))


if __name__ == "__main__":
    run_all()
    print("PASS privacy_scan tests")

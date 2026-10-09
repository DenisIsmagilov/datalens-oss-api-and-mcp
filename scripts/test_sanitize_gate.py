import subprocess
import sys
import tempfile
from pathlib import Path

GATE = Path(__file__).with_name("sanitize_gate.py")
HOST = "datalens.fs." + "local"
SECRET_KEY = "DL_API_" + "TOKEN"


def run(root: Path, secrets: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GATE), "--root", str(root), "--secrets-from", str(secrets)],
        text=True,
        capture_output=True,
    )


def test_host_fails() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw) / "tree"
        secrets = Path(raw) / "src"
        root.mkdir()
        secrets.mkdir()
        (root / "a.txt").write_text("see " + HOST + "\n", encoding="utf-8")
        (secrets / "docker-compose.realprod.yaml").write_text("services: {}\n", encoding="utf-8")
        result = run(root, secrets)
        assert result.returncode == 1, result.stdout + result.stderr
        assert HOST not in result.stdout
        assert "rule:host" in result.stdout
        assert "a.txt" in result.stdout


def test_split_example_is_allowed() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw) / "tree"
        secrets = Path(raw) / "src"
        doc = root / "datalens-neuro" / "formula-docs"
        doc.mkdir(parents=True)
        secrets.mkdir()
        ip = "192." + "168.0.1"
        (doc / "SPLIT.md").write_text(
            'SPLIT("' + ip + '", ".", 1) = "192"\n'
            'SPLIT("' + ip + '") = "' + ip + '"\n',
            encoding="utf-8",
        )
        (secrets / "docker-compose.realprod.yaml").write_text("services: {}\n", encoding="utf-8")
        result = run(root, secrets)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "exception: datalens-neuro/formula-docs/SPLIT.md" in result.stdout


def test_other_ip_fails() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw) / "tree"
        secrets = Path(raw) / "src"
        root.mkdir()
        secrets.mkdir()
        (root / "note.md").write_text("192." + "168.0.1\n", encoding="utf-8")
        (secrets / "docker-compose.realprod.yaml").write_text("services: {}\n", encoding="utf-8")
        result = run(root, secrets)
        assert result.returncode == 1
        assert "rule:ip" in result.stdout
        assert "note.md" in result.stdout


def test_secret_value_fails_without_printing_it() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw) / "tree"
        secrets = Path(raw) / "src"
        root.mkdir()
        secrets.mkdir()
        value = "super-secret-value"
        (root / "leak.txt").write_text(value + "\n", encoding="utf-8")
        (secrets / ".env").write_text(f"{SECRET_KEY}={value}\n", encoding="utf-8")
        (secrets / "docker-compose.realprod.yaml").write_text("services: {}\n", encoding="utf-8")
        result = run(root, secrets)
        assert result.returncode == 1
        assert value not in result.stdout
        assert value not in result.stderr
        assert "rule:secret" in result.stdout


def test_yaml_quoted_equals_is_full_needle() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw) / "tree"
        secrets = Path(raw) / "src"
        root.mkdir()
        secrets.mkdir()
        body = "abcdefghij" + "=short"
        (root / "leak.txt").write_text(body + "\n", encoding="utf-8")
        (secrets / "docker-compose.realprod.yaml").write_text(
            'TOKEN_PRIVATE_KEY: "' + body + '"\n',
            encoding="utf-8",
        )
        result = run(root, secrets)
        assert result.returncode == 1, result.returncode
        assert "rule:secret" in result.stdout
        assert "name:TOKEN_PRIVATE_KEY" in result.stdout
        assert "abcdefghij" not in result.stdout
        assert "abcdefghij" not in result.stderr


def test_highcharts_dir_fails() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw) / "tree"
        secrets = Path(raw) / "src"
        (root / "highcharts").mkdir(parents=True)
        secrets.mkdir()
        (root / "highcharts" / "a.js").write_text("x\n", encoding="utf-8")
        (secrets / "docker-compose.realprod.yaml").write_text("services: {}\n", encoding="utf-8")
        result = run(root, secrets)
        assert result.returncode == 1
        assert "rule:highcharts" in result.stdout


if __name__ == "__main__":
    test_host_fails()
    test_split_example_is_allowed()
    test_other_ip_fails()
    test_secret_value_fails_without_printing_it()
    test_yaml_quoted_equals_is_full_needle()
    test_highcharts_dir_fails()
    print("ok")

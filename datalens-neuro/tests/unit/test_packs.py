from pathlib import Path

from app import semantic
from app.packs import load_packs

PACKS = "/app/packs"


def _write_pack(root: Path, name: str, manifest: str, files: dict[str, str] | None = None) -> None:
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "pack.yaml").write_text(manifest, encoding="utf-8")
    for filename, content in (files or {}).items():
        (directory / filename).write_text(content, encoding="utf-8")


def test_bundled_packs_load():
    registry = load_packs(PACKS)
    assert registry.errors == {}
    assert set(registry.packs) == {"default", "demo"}
    demo = registry.get("demo")
    assert demo.workbook_ids == ["wb-demo"]
    assert "только чтение" in demo.prompt
    assert demo.datasets_by_id["ds-demo"]["name"] == "Демо продажи"
    default = registry.get("default")
    assert default.workbook_ids == [] and default.prompt == ""
    assert default.in_scope("any-workbook")


def test_broken_pack_does_not_block_others(tmp_path):
    _write_pack(tmp_path, "good", "name: good\nworkbookIds: [wb1]\n")
    _write_pack(tmp_path, "bad", "name: bad\nglossary: missing.yaml\n")
    _write_pack(tmp_path, "wrongname", "name: other\n")
    _write_pack(tmp_path, "escape", "name: escape\nprompt: ../good/pack.yaml\n")
    (tmp_path / "notapack").mkdir()
    registry = load_packs(str(tmp_path))
    assert set(registry.packs) == {"good"}
    assert set(registry.errors) == {"bad", "wrongname", "escape"}
    assert "missing.yaml" in registry.errors["bad"]
    good = registry.get("good")
    assert good.in_scope("wb1") and not good.in_scope("wb2") and not good.in_scope(None)


def test_missing_packs_dir(tmp_path):
    registry = load_packs(str(tmp_path / "nope"))
    assert registry.packs == {} and "*" in registry.errors


def test_semantic_search_finds_intent_without_sql():
    pack = load_packs(PACKS).get("demo")
    result = semantic.search(pack, "продажи на маркетплейсах")
    intent = next(item for item in result["intents"] if item["id"] == "demo_sales")
    assert intent["dataset_id"] == "ds-demo"
    assert not {"sql_hint", "table", "triggers"} & set(intent)
    assert result["businessRules"] == ["правило демо"]
    assert result["availableIntents"] == ["demo_sales"]


def test_semantic_search_matches_synonym_terms():
    pack = load_packs(PACKS).get("demo")
    result = semantic.search(pack, "свободный остаток по складам")
    assert "свободный остаток" in [term["term"] for term in result["terms"]]


def test_get_intent():
    pack = load_packs(PACKS).get("demo")
    intent = semantic.get_intent(pack, "demo_sales")
    assert intent["dataset_id"] == "ds-demo" and "sql_hint" not in intent
    assert semantic.get_intent(pack, "nope") is None


def test_search_on_empty_pack():
    pack = load_packs(PACKS).get("default")
    result = semantic.search(pack, "что угодно")
    assert result["intents"] == [] and result["datasets"] == [] and result["availableIntents"] == []

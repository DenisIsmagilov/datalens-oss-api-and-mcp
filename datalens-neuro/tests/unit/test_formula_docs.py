from pathlib import Path

from app.formula.docs import FIELD_REF_FALLBACK, load_docs, select_fragments


def test_select_prefers_heading_then_shorter(tmp_path: Path):
    root = tmp_path
    (root / "agg.md").write_text("# SUM\nСумма значений поля\n\n# AVG\nСреднее\n", encoding="utf-8")
    (root / "_field-ref.md").write_text("Поле пишется как [Заголовок].\n", encoding="utf-8")
    fixed, fragments = load_docs(root)
    assert "Заголовок" in fixed
    picked = select_fragments("посчитай SUM выручки", fragments, limit=8, max_chars=6000)
    assert picked[0].title == "SUM"
    assert "AVG" not in {item.title for item in picked}


def test_load_splits_h1_and_h2(tmp_path: Path):
    (tmp_path / "fn.md").write_text(
        "---\ntitle: meta\n---\n\n# Главная\nintro\n\n## Раздел A\na\n\n## Раздел B\nb\n",
        encoding="utf-8",
    )
    _, fragments = load_docs(tmp_path)
    titles = [f.title for f in fragments]
    assert titles == ["Главная", "Раздел A", "Раздел B"]


def test_load_skips_overview_indexes(tmp_path: Path):
    (tmp_path / "all.md").write_text("# Все функции\n\n## foo\n", encoding="utf-8")
    (tmp_path / "aggregation-functions.md").write_text("# Агрегации\n", encoding="utf-8")
    (tmp_path / "SUM.md").write_text("# SUM\nСумма\n", encoding="utf-8")
    _, fragments = load_docs(tmp_path)
    titles = {f.title for f in fragments}
    assert "SUM" in titles
    assert "Все функции" not in titles
    assert "Агрегации" not in titles


def test_select_respects_count_and_chars():
    from app.formula.docs import Fragment

    fragments = [Fragment(title=f"F{i}", body="слово " + ("x" * 100)) for i in range(10)]
    picked = select_fragments("слово", fragments, limit=2, max_chars=250)
    assert len(picked) <= 2
    assert sum(len(item.body) for item in picked) <= 250


def test_missing_field_ref_uses_fallback(tmp_path: Path):
    fixed, fragments = load_docs(tmp_path)
    assert fixed == FIELD_REF_FALLBACK
    assert fragments == []


def test_snapshot_is_in_the_image():
    root = Path("/app/formula-docs")
    text = (root / "SOURCE.md").read_text(encoding="utf-8")
    assert "github.com/datalens-tech/docs" in text
    assert "commit:" in text
    pages = [p for p in root.rglob("*.md") if p.name not in {"SOURCE.md", "_field-ref.md"}]
    assert pages
    _, fragments = load_docs(root)
    titles = {f.title for f in fragments}
    assert "Все функции" not in titles
    assert any("SUM" in t for t in titles)

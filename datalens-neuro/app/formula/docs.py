import re
from dataclasses import dataclass
from pathlib import Path

FIELD_REF_FALLBACK = "Поле в формуле пишется как [Заголовок]."
_WORD = re.compile(r"\w+", re.UNICODE)
_HEADING = re.compile(r"(?m)^#{1,2}\s+")
_SKIP_FRAGMENT_FILES = {"_field-ref.md", "SOURCE.md", "all.md"}


def _without_preamble(text: str) -> str:
    match = _HEADING.search(text)
    if not match:
        return ""
    return text[match.start() :]


@dataclass(frozen=True)
class Fragment:
    title: str
    body: str


def _words(text: str) -> set[str]:
    return {item.lower() for item in _WORD.findall(text)}


def load_docs(root: Path) -> tuple[str, list[Fragment]]:
    field_ref = root / "_field-ref.md"
    if field_ref.is_file():
        fixed = field_ref.read_text(encoding="utf-8").strip()[:500]
    else:
        fixed = FIELD_REF_FALLBACK
    fragments: list[Fragment] = []
    if not root.is_dir():
        return fixed, fragments
    for path in sorted(root.rglob("*.md")):
        if path.name in _SKIP_FRAGMENT_FILES or path.name.endswith("-functions.md"):
            continue
        text = _without_preamble(path.read_text(encoding="utf-8"))
        if not text:
            continue
        parts = _HEADING.split(text)
        for part in parts:
            body = part.strip()
            if not body:
                continue
            title, _, rest = body.partition("\n")
            fragments.append(Fragment(title=title.strip()[:200], body=(rest or body).strip()))
    return fixed, fragments


def select_fragments(question: str, fragments: list[Fragment], *, limit: int, max_chars: int) -> list[Fragment]:
    wanted = _words(question)
    ranked = sorted(
        fragments,
        key=lambda item: (
            -len(wanted & _words(item.title + " " + item.body)),
            -len(wanted & _words(item.title)),
            len(item.body),
            item.title,
        ),
    )
    chosen: list[Fragment] = []
    total = 0
    for item in ranked:
        if not (wanted & _words(item.title + " " + item.body)):
            continue
        if len(chosen) >= limit:
            break
        piece = item
        if total + len(item.body) > max_chars:
            room = max_chars - total
            if room <= 0:
                break
            piece = Fragment(item.title, item.body[:room])
        chosen.append(piece)
        total += len(piece.body)
        if total >= max_chars:
            break
    return chosen

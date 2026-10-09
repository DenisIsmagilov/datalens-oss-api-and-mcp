import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

logger = logging.getLogger("datalens_neuro.packs")


class PackManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    title: str = ""
    workbookIds: list[str] = Field(default_factory=list)
    prompt: str | None = None
    glossary: str | None = None
    catalog: str | None = None


@dataclass
class Pack:
    name: str
    title: str
    workbook_ids: list[str]
    prompt: str = ""
    glossary: dict[str, Any] = field(default_factory=dict)
    catalog: dict[str, Any] = field(default_factory=dict)
    datasets_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    datasets_by_name: dict[str, dict[str, Any]] = field(default_factory=dict)

    def in_scope(self, workbook_id: str | None) -> bool:
        return not self.workbook_ids or workbook_id in self.workbook_ids


@dataclass
class PackRegistry:
    packs: dict[str, Pack] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)

    def get(self, name: str) -> Pack | None:
        return self.packs.get(name)


def _pack_file(directory: Path, relative: str) -> Path:
    path = (directory / relative).resolve()
    if directory.resolve() not in path.parents:
        raise ValueError(f"path escapes pack dir: {relative}")
    if not path.is_file():
        raise ValueError(f"file not found: {relative}")
    return path


def load_pack(directory: Path) -> Pack:
    raw = yaml.safe_load((directory / "pack.yaml").read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("pack.yaml must be a mapping")
    manifest = PackManifest.model_validate(raw)
    if manifest.name != directory.name:
        raise ValueError(f"pack name {manifest.name!r} != directory {directory.name!r}")
    prompt = ""
    if manifest.prompt:
        prompt = _pack_file(directory, manifest.prompt).read_text(encoding="utf-8").strip()
    glossary: Any = {}
    if manifest.glossary:
        glossary = yaml.safe_load(_pack_file(directory, manifest.glossary).read_text(encoding="utf-8")) or {}
        if not isinstance(glossary, dict):
            raise ValueError("glossary must be a mapping")
    catalog: Any = {}
    if manifest.catalog:
        catalog = json.loads(_pack_file(directory, manifest.catalog).read_text(encoding="utf-8"))
        if not isinstance(catalog, dict):
            raise ValueError("catalog must be an object")
    by_id: dict[str, dict[str, Any]] = {}
    by_name: dict[str, dict[str, Any]] = {}
    for card in catalog.get("datasets") or []:
        if not isinstance(card, dict):
            continue
        if card.get("entryId"):
            by_id[str(card["entryId"])] = card
        if card.get("name"):
            by_name[str(card["name"]).strip().lower()] = card
    return Pack(
        name=manifest.name,
        title=manifest.title,
        workbook_ids=list(manifest.workbookIds),
        prompt=prompt,
        glossary=glossary,
        catalog=catalog,
        datasets_by_id=by_id,
        datasets_by_name=by_name,
    )


def load_packs(root: str) -> PackRegistry:
    registry = PackRegistry()
    base = Path(root)
    if not base.is_dir():
        registry.errors["*"] = f"packs dir not found: {root}"
        logger.warning(registry.errors["*"])
        return registry
    for directory in sorted(path for path in base.iterdir() if path.is_dir()):
        if not (directory / "pack.yaml").is_file():
            continue
        try:
            pack = load_pack(directory)
        except (OSError, ValueError, ValidationError, yaml.YAMLError) as exc:
            registry.errors[directory.name] = f"{type(exc).__name__}: {exc}"[:500]
            logger.warning("pack %s failed to load: %s", directory.name, registry.errors[directory.name])
            continue
        registry.packs[pack.name] = pack
    return registry

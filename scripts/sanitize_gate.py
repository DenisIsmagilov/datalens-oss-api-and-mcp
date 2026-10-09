#!/usr/bin/env python3
"""Гейт публичного дерева. Значения секретов в stdout/stderr не пишет."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HOST = "datalens.fs." + "local"
GITLAB = "gitlab." + "fs" + "tech"
ORG = "fs" + "tech"
SELLER = "seller" + "stats"
SELLER_TITLE = "Seller" + "Stats"
FOTO = "Foto" + "sklad"
FOTO_LOW = "foto" + "sklad"
WORKBOOK = "4q6xjacqie" + "eoq"
IP = "192." + "168."
SPLIT_MARK = 'SPLIT("' + "192." + "168.0.1" + '"'
MARKET = ("Wild" + "berries", "Oz" + "on", "маркет" + "плейс")
SECRET_NAME = re.compile(r"(TOKEN|PASSWORD|SECRET|API_KEY)", re.I)
SKIP_VALUES = {"", "change-me", "us-master-token", "admin"}


def literals() -> list[tuple[str, str]]:
    return [
        ("host", HOST),
        ("gitlab", GITLAB),
        ("org", ORG),
        ("seller", SELLER),
        ("seller-title", SELLER_TITLE),
        ("foto", FOTO),
        ("foto-low", FOTO_LOW),
        ("workbook", WORKBOOK),
    ]


def secret_values(src: Path) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    files = [src / "docker-compose.realprod.yaml"]
    files.extend(src.glob(".env"))
    files.extend(src.glob(".env.*"))
    for path in files:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip().startswith("#") or ":" not in line and "=" not in line:
                continue
            eq = line.find("=")
            colon = line.find(":")
            if eq >= 0 and (colon < 0 or eq < colon):
                key, _, raw = line.partition("=")
            else:
                key, _, raw = line.partition(":")
            key = key.strip().strip('"').strip("'")
            if not SECRET_NAME.search(key):
                continue
            value = raw.strip().strip('"').strip("'")
            if len(value) <= 8 or value in SKIP_VALUES or value.startswith("${"):
                continue
            found.append((key, value))
    return found


def walk_text(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if "highcharts" in path.parts:
            yield path, None
            continue
        data = path.read_bytes()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("utf-8", errors="replace")
        yield path, text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--secrets-from", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    hits: list[str] = []
    exception_printed = False
    for path, text in walk_text(root):
        rel = path.relative_to(root).as_posix()
        if text is None or "highcharts" in Path(rel).parts:
            hits.append(f"rule:highcharts path:{rel}")
            continue
        if path.name == "eval_questions.yaml":
            for word in MARKET:
                if word in text:
                    hits.append(f"rule:eval path:{rel}")
                    break
        for rule, needle in literals():
            if needle in text:
                hits.append(f"rule:{rule} path:{rel}")
        if IP in text:
            if rel == "datalens-neuro/formula-docs/SPLIT.md":
                kept = "\n".join(line for line in text.splitlines() if SPLIT_MARK not in line)
                if IP not in kept:
                    if not exception_printed:
                        print("exception: datalens-neuro/formula-docs/SPLIT.md")
                        exception_printed = True
                else:
                    hits.append(f"rule:ip path:{rel}")
            else:
                hits.append(f"rule:ip path:{rel}")
        for key, value in secret_values(args.secrets_from):
            if value in text:
                hits.append(f"rule:secret name:{key} path:{rel}")
    if hits:
        for line in hits:
            print(line)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

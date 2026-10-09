#!/bin/sh
# Скачивает справочник функций DataLens в formula-docs/ рядом с этим репозиторием модуля.
# Коммит и путь читаются из formula-docs/SOURCE.md. SOURCE.md и _field-ref.md не затираются.
# У исходного репозитория нет файла LICENSE: страницы не коммитятся, их забирает тот, кто запускает скрипт.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
SOURCE="$ROOT/formula-docs/SOURCE.md"
DEST=${FORMULA_DOCS_DEST:-$ROOT/formula-docs}

if [ ! -f "$SOURCE" ]; then
  echo "fetch-formula-docs: нет $SOURCE" >&2
  exit 1
fi

url=$(sed -n 's/^url: //p' "$SOURCE")
commit=$(sed -n 's/^commit: //p' "$SOURCE")
rel=$(sed -n 's/^path: //p' "$SOURCE")

case "$url" in
  https://github.com/datalens-tech/docs) ;;
  *)
    echo "fetch-formula-docs: неожиданный url в SOURCE.md" >&2
    exit 1
    ;;
esac

if [ -z "$commit" ] || [ -z "$rel" ]; then
  echo "fetch-formula-docs: в SOURCE.md нет commit или path" >&2
  exit 1
fi

tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT

curl -fsSL "https://codeload.github.com/datalens-tech/docs/tar.gz/${commit}" -o "$tmpdir/docs.tgz"
tar -xzf "$tmpdir/docs.tgz" -C "$tmpdir"

top=$(find "$tmpdir" -mindepth 1 -maxdepth 1 -type d)
src="$top/$rel"
if [ ! -d "$src" ]; then
  echo "fetch-formula-docs: в архиве нет $rel" >&2
  exit 1
fi

find "$src" -type f -name '*.md' | while IFS= read -r file; do
  relpath=${file#"$src"/}
  mkdir -p "$DEST/$(dirname "$relpath")"
  cp "$file" "$DEST/$relpath"
done

count=$(find "$DEST" -type f -name '*.md' ! -name 'SOURCE.md' ! -name '_field-ref.md' | wc -l)
echo "fetch-formula-docs: страниц в $DEST: $count"

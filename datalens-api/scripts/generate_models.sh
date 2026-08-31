#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT/datalens-api"
python scripts/prepare_openapi.py \
  --input "$ROOT/docs/superpowers/reference/datalens-cloud-openapi.json" \
  --output app/models/openapi.prepared.json
datamodel-codegen \
  --input app/models/openapi.prepared.json \
  --input-file-type openapi \
  --output app/models/generated.py \
  --output-model-type pydantic_v2.BaseModel \
  --target-python-version 3.12 \
  --use-standard-collections \
  --use-union-operator \
  --collapse-root-models \
  --disable-timestamp

# Переменные

Образец — корневой `env.example`. Файл `.env` не коммитится. Ниже каждая переменная образца и значение, которое в нём записано.

Для `NEURO_UI_ENABLED`: для профиля `panel` поставьте `true`, иначе `/ui/loader.js` отдаёт заглушку.

| Переменная | Значение в `env.example` |
|---|---|
| `DATALENS_NETWORK` | `datalens_default` |
| `DL_API_TOKEN` | `change-me` |
| `US_MASTER_TOKEN` | `us-master-token` |
| `US_HOST` | `http://us:8080` |
| `CONTROL_API_HOST` | `http://control-api:8080` |
| `META_MANAGER_HOST` | `http://meta-manager:8080` |
| `UI_API_HOST` | `http://ui-api:8080` |
| `DATA_API_HOST` | `http://data-api:8080` |
| `CHARTS_HOST` | `http://ui:8080` |
| `DATA_MAX_ROWS` | `500` |
| `DATA_MAX_DISTINCT` | `200` |
| `DATA_MAX_CELL_CHARS` | `500` |
| `DATA_QUERY_TIMEOUT_SEC` | `60` |
| `DATALENS_API_PORT` | `8393` |
| `DATALENS_API_VERSION_DEFAULT` | `2` |
| `US_TENANT_ID` | `common` |
| `AUTH_HOST` | `http://auth:8080` |
| `AUTH_LOGIN` | `admin` |
| `AUTH_PASSWORD` | `admin` |
| `MCP_AUTH_TOKEN` | `change-me` |
| `DATALENS_API_HOST` | `http://datalens-api:8393` |
| `DATALENS_MCP_PORT` | `8394` |
| `DATALENS_API_VERSION` | `2` |
| `DATALENS_API_TIMEOUT_SEC` | `90` |
| `NEURO_ENABLED` | `true` |
| `NEURO_UI_ENABLED` | `false` |
| `NEURO_UI_TITLE` | `Нейроаналитик` |
| `NEURO_UI_ROLES` | `datalens.admin,datalens.editor` |
| `NEURO_UI_ORIGINS` | `http://127.0.0.1:8080` |
| `NEURO_UI_CONVERSATION_IDLE_HOURS` | `6` |
| `AUTH_TOKEN_PUBLIC_KEY` | пусто |
| `NEURO_PORT` | `8396` |
| `NEURO_API_TOKEN` | `change-me` |
| `NEURO_DEFAULT_PACK` | `default` |
| `NEURO_PACKS_DIR` | `/packs` |
| `NEURO_DB_PATH` | `/data/neuro.sqlite` |
| `NEURO_TIMEZONE` | `Europe/Moscow` |
| `NEURO_HISTORY_MESSAGES` | `10` |
| `NEURO_MAX_ROUNDS` | `15` |
| `NEURO_DEADLINE_SEC` | `150` |
| `NEURO_FORMULA_ATTEMPTS` | `3` |
| `NEURO_FORMULA_DOC_FRAGMENTS` | `8` |
| `NEURO_FORMULA_DOC_CHARS` | `6000` |
| `NEURO_TOOL_RESULT_MAX_CHARS` | `12000` |
| `NEURO_CONVERSATION_TTL_DAYS` | `30` |
| `NEURO_RATE_LIMIT_PER_MIN` | `30` |
| `LLM_PROVIDER` | `openai_compatible` |
| `LLM_BASE_URL` | `https://api.deepseek.com` |
| `LLM_MODEL` | `deepseek-v4-flash` |
| `LLM_API_KEY` | пусто |
| `LLM_TIMEOUT_SEC` | `120` |
| `LLM_MAX_RETRIES` | `2` |
| `DATALENS_UI_PORT` | `8080` |
| `DATALENS_UI_UPSTREAM` | `http://ui:8080` |
| `NEURO_PUBLIC_ORIGIN` | `http://127.0.0.1:8396` |

`AUTH_TOKEN_PUBLIC_KEY` заполняете публичным ключом своего `datalens-auth`. `LLM_API_KEY` — ключ вашего LLM-провайдера. Оба в репозиторий не кладутся.

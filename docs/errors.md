# Типичные ошибки

| Симптом | Что проверить |
|---|---|
| `datalens-api` не стартует / `network not found` | `DATALENS_NETWORK` = имя из `docker network ls`. Сеть должна уже существовать (DataLens запущен). |
| API `health` ок, RPC таймаут / connection refused к `us` | Контейнер не в сети DataLens, или хост `US_HOST` не `http://us:8080`. |
| HTTP 401 на `/rpc/*` | `Authorization: Bearer` совпадает с `DL_API_TOKEN` в `.env` API. |
| HTTP 401 на `/mcp` | Bearer = `MCP_AUTH_TOKEN`, не `DL_API_TOKEN`. |
| MCP `health` ок, tools падают | `datalens-api` не запущен; `DATALENS_API_HOST` внутри сети должен быть `http://datalens-api:8393`. |
| Методы есть, ответы «не как в облаке» / 5xx на charts | Стек не 2.9.0, или другой набор сервисов (нет `auth` / `control-api` / `meta-manager`). |
| `getWorkbookExportResult` → 400 | Экспорт ещё не `success`; сначала `getWorkbookExportStatus`. |
| Wizard `/wizard` белый экран после create | Нужен API с записью `data.shared` строкой (релиз 0.2). Пересоберите `datalens-api`. Уже созданный чарт: update с тем же `data` или delete+create. |
| `updateWizardChart` → `INVALID_ARGUMENT` | Табличный vis на `graph_wizard_node` (или `line` на таблице). Создайте новый чарт, type на update не меняется. |

Логи: `docker compose logs datalens-api` и `docker compose logs datalens-mcp`.

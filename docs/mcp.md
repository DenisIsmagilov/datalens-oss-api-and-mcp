# MCP

Контейнер `datalens-mcp` — тонкая обёртка: tools → `POST /rpc/<method>` на `datalens-api`. Бизнес-логику DataLens не дублирует.

Транспорт: **только Streamable HTTP**. stdio нет.

- URL: `http://127.0.0.1:8394/mcp`
- Auth: `Authorization: Bearer <MCP_AUTH_TOKEN>`
- Health без токена: `GET http://127.0.0.1:8394/health`

Без/с неверным Bearer на `/mcp` → HTTP 401.

## Tools (28)

**Мета (2):**

| Tool | Поведение |
|---|---|
| `list_rpc_methods` | `GET {DATALENS_API_HOST}/json/` → список RPC |
| `call_rpc` | аргументы `method` (str), `args` (object) → `POST /rpc/{method}` |

`call_rpc` — путь к update/delete/move, create workbook/collection/connection/dataset, start/cancel export и import. Не отдавайте его агенту без контроля.

**Чтение, shortcuts (23):**  
`get_workbooks_list`, `get_workbook`, `get_workbooks_by_ids`, `get_workbook_entries`, `get_collection`, `get_collections_by_ids`, `get_collection_content`, `get_collection_breadcrumbs`, `get_root_collection_permissions`, `get_entries`, `list_directory`, `get_entries_relations`, `get_entries_permissions`, `get_permissions`, `get_connection`, `get_dataset`, `validate_dataset`, `get_dashboard`, `get_wizard_chart`, `get_ql_chart`, `get_workbook_export_status`, `get_workbook_export_result`, `get_workbook_import_status`

Имена tools — snake_case, внутри camelCase RPC. Аргументы = JSON Args того же метода. `getWorkbooksList.page` — **0-based**. У wizard/QL get: аргумент `chartId`, не `entryId`.

**Создание, shortcuts (3):** `create_dashboard` → `createDashboard`; `create_wizard_chart` → `createWizardChart`; `create_ql_chart` → `createQLChart`.

Update/delete чартов и дашбордов — только `call_rpc`.

## Cursor

```json
{
  "mcpServers": {
    "datalens-oss": {
      "url": "http://127.0.0.1:8394/mcp",
      "headers": {
        "Authorization": "Bearer ${env:MCP_AUTH_TOKEN}"
      }
    }
  }
}
```

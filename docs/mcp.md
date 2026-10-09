# MCP

Вызов: `POST /mcp`, транспорт Streamable HTTP.

- URL: `http://127.0.0.1:8394/mcp`
- Заголовок: `Authorization: Bearer <MCP_AUTH_TOKEN>`

Список tools снят с кода (`datalens-mcp/app/registry.py`; первыми идут `list_rpc_methods` и `call_rpc`):

- `list_rpc_methods`
- `call_rpc`
- `get_workbooks_list`
- `get_workbook`
- `get_workbooks_by_ids`
- `get_workbook_entries`
- `get_collection`
- `get_collections_by_ids`
- `get_collection_content`
- `get_collection_breadcrumbs`
- `get_root_collection_permissions`
- `get_entries`
- `list_directory`
- `get_entries_relations`
- `get_entries_permissions`
- `get_permissions`
- `get_connection`
- `get_dataset`
- `validate_dataset`
- `get_dashboard`
- `get_wizard_chart`
- `get_ql_chart`
- `get_workbook_export_status`
- `get_workbook_export_result`
- `get_workbook_import_status`
- `create_dashboard`
- `create_wizard_chart`
- `create_ql_chart`
- `query_dataset`
- `get_dataset_field_values`
- `get_chart_data`

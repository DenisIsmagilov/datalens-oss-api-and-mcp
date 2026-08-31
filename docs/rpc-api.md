# RPC API

Эндпоинт: `POST /rpc/<method>`. Контракт близок к облачному DataLens API 2.

## Заголовки

| Заголовок | Значение |
|---|---|
| `Authorization` | `Bearer <DL_API_TOKEN>` |
| `Content-Type` | `application/json` |
| `x-dl-api-version` | `2` (или `latest` → `2`) |

`x-dl-org-id` можно не передавать (OSS single-tenant).

Служебные:

- `GET /health` → `{"status":"ok"}`
- `GET /json/` — OpenAPI только **реализованных** методов

## Реализованные методы (57)

**Collection:** `createCollection`, `getCollection`, `updateCollection`, `deleteCollection`, `deleteCollections`, `moveCollection`, `moveCollections`, `getCollectionsByIds`, `getCollectionContent`, `getCollectionBreadcrumbs`, `getRootCollectionPermissions`

**Workbook:** `createWorkbook`, `getWorkbook`, `updateWorkbook`, `deleteWorkbook`, `deleteWorkbooks`, `moveWorkbook`, `moveWorkbooks`, `getWorkbooksList`, `getWorkbooksByIds`, `getWorkbookEntries`

**Entries / navigation / folder:** `getEntries`, `listDirectory`, `getEntriesRelations`, `getEntriesPermissions`, `renameEntry`, `createFolder`, `deleteFolder`, `moveFolderEntry`, `getPermissions`

**Connection / Dataset:** `createConnection`, `getConnection`, `updateConnection`, `deleteConnection`, `createDataset`, `getDataset`, `updateDataset`, `deleteDataset`, `validateDataset`

**Dashboard / Wizard / QL:** `createDashboard`, `getDashboard`, `updateDashboard`, `deleteDashboard`, `createWizardChart`, `getWizardChart`, `updateWizardChart`, `deleteWizardChart`, `createQLChart`, `getQLChart`, `updateQLChart`, `deleteQLChart`

**Transfer:** `startWorkbookExport`, `getWorkbookExportStatus`, `getWorkbookExportResult`, `cancelWorkbookExport`, `startWorkbookImport`, `getWorkbookImportStatus`

Неизвестное имя метода → `404 NOT_FOUND`. Неверный Bearer → `401`.

## Примеры

```bash
# список воркбуков (page 0-based)
curl -X POST "http://127.0.0.1:8393/rpc/getWorkbooksList" \
  -H "Authorization: Bearer ${DL_API_TOKEN}" \
  -H "x-dl-api-version: 2" \
  -H "Content-Type: application/json" \
  -d '{"page":0,"pageSize":10}'

# воркбук по id
curl -X POST "http://127.0.0.1:8393/rpc/getWorkbook" \
  -H "Authorization: Bearer ${DL_API_TOKEN}" \
  -H "x-dl-api-version: 2" \
  -H "Content-Type: application/json" \
  -d '{"workbookId":"'"${WORKBOOK_ID}"'"}'

# датасет
curl -X POST "http://127.0.0.1:8393/rpc/getDataset" \
  -H "Authorization: Bearer ${DL_API_TOKEN}" \
  -H "x-dl-api-version: 2" \
  -H "Content-Type: application/json" \
  -d '{"datasetId":"'"${DATASET_ID}"'"}'
```

В примерах нет реальных токенов. `DL_API_TOKEN` берите из своего `.env`.

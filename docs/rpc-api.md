# RPC API

Вызов: `POST /rpc/<method>`.

Заголовки: `Authorization: Bearer <DL_API_TOKEN>`, `x-dl-api-version: 2`, `Content-Type: application/json`.

Базовый адрес на этой машине: `http://127.0.0.1:8393`.

Список методов снят с регистрации в коде (`datalens-api/app/methods/__init__.py`):

- `createCollection`
- `getCollection`
- `updateCollection`
- `deleteCollection`
- `deleteCollections`
- `moveCollection`
- `moveCollections`
- `getCollectionsByIds`
- `getCollectionContent`
- `getCollectionBreadcrumbs`
- `getRootCollectionPermissions`
- `getWorkbooksList`
- `createWorkbook`
- `getWorkbook`
- `updateWorkbook`
- `deleteWorkbook`
- `deleteWorkbooks`
- `moveWorkbook`
- `moveWorkbooks`
- `getWorkbooksByIds`
- `getWorkbookEntries`
- `getEntriesRelations`
- `renameEntry`
- `getEntriesPermissions`
- `getEntries`
- `listDirectory`
- `createFolder`
- `deleteFolder`
- `moveFolderEntry`
- `getPermissions`
- `createConnection`
- `getConnection`
- `updateConnection`
- `deleteConnection`
- `createDataset`
- `getDataset`
- `updateDataset`
- `deleteDataset`
- `validateDataset`
- `validateDatasetFormula`
- `createDashboard`
- `getDashboard`
- `updateDashboard`
- `deleteDashboard`
- `createWizardChart`
- `getWizardChart`
- `updateWizardChart`
- `deleteWizardChart`
- `createQLChart`
- `getQLChart`
- `updateQLChart`
- `deleteQLChart`
- `startWorkbookExport`
- `getWorkbookExportStatus`
- `getWorkbookExportResult`
- `cancelWorkbookExport`
- `startWorkbookImport`
- `getWorkbookImportStatus`
- `queryDataset`
- `getDatasetFieldValues`
- `getChartData`

## Примеры

Оба вызова — методы чтения из списка выше. В теле нет секретов: `workbookId` замените на свой.

```bash
curl -sS http://127.0.0.1:8393/rpc/getWorkbook \
  -H "Authorization: Bearer <DL_API_TOKEN>" \
  -H "x-dl-api-version: 2" \
  -H "Content-Type: application/json" \
  -d '{"workbookId":"change-me"}'
```

```bash
curl -sS http://127.0.0.1:8393/rpc/getWorkbookEntries \
  -H "Authorization: Bearer <DL_API_TOKEN>" \
  -H "x-dl-api-version: 2" \
  -H "Content-Type: application/json" \
  -d '{"workbookId":"change-me"}'
```

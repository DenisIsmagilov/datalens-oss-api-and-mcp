# Changelog

## 0.2.0 — 2026-09-14

Wizard-таблицы, которые создаёт API, открываются в DataLens UI `/wizard`.

- `createWizardChart`: `visualization.id` `flatTable` / `pivotTable` / `table` → US `table_wizard_node` (это уже было в 0.1).
- На create и `updateWizardChart` `data.shared` в US пишется **JSON-строкой**, как делает UI. Агент по-прежнему может слать object.
- Смена семейства vis на update → `400 INVALID_ARGUMENT`; US `type` на update не меняется.

После обновления пересоберите контейнер `datalens-api`. Чарт, созданный старым API, сам не починится — `updateWizardChart` с тем же `data` или delete+create.

## 0.1.0 — 2026-08-31

Первая публичная выкладка: `datalens-api` + `datalens-mcp`, установка рядом с уже работающим DataLens OSS 2.9.0.

# Ошибки

| Симптом | Причина |
|---|---|
| Контейнер не резолвит `us` | Не та сеть. `DATALENS_NETWORK` должен совпадать с именем из `docker network ls`, DataLens уже запущен. |
| Порт `DATALENS_UI_PORT` занят | Сервис `ui` всё ещё публикует этот порт на хост. Снимите публикацию в compose DataLens и запустите DataLens снова, затем профиль `panel`. Прокси чужой процесс сам не подменяет. |
| 401 | Запрос без токена или с неверным Bearer. API ждёт `DL_API_TOKEN`, MCP — `MCP_AUTH_TOKEN`, `POST /v1/chat` — `NEURO_API_TOKEN`. |
| Панель пустая | Не задан `NEURO_PUBLIC_ORIGIN`, либо `NEURO_UI_ENABLED` не `true`. Без `true` адрес `/ui/loader.js` отдаёт заглушку, и кнопка не появляется. |

Логи: `docker compose logs datalens-api`, `docker compose logs datalens-mcp`, `docker compose logs datalens-neuro`.

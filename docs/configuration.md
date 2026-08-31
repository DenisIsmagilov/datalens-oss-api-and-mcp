# Конфигурация

Все значения — переменные окружения. Образец: корневой `env.example`. Файл `.env` в git не попадает.

## Сеть и порты

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `DATALENS_NETWORK` | `datalens_default` | Имя **существующей** docker-сети DataLens |
| `DATALENS_API_PORT` | `8393` | Публикация `datalens-api` |
| `DATALENS_MCP_PORT` | `8394` | Публикация `datalens-mcp` |

## datalens-api

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `DL_API_TOKEN` | — | Bearer клиентов API (обязателен) |
| `US_MASTER_TOKEN` | — | Master-токен OSS `us` (обязателен) |
| `US_HOST` | `http://us:8080` | DNS внутри сети DataLens |
| `CONTROL_API_HOST` | `http://control-api:8080` | connections / datasets |
| `META_MANAGER_HOST` | `http://meta-manager:8080` | export / import воркбуков |
| `UI_API_HOST` | `http://ui-api:8080` | зарезервирован в настройках |
| `AUTH_HOST` | `http://auth:8080` | JWT для control-api |
| `AUTH_LOGIN` | `admin` | Логин сервиса auth |
| `AUTH_PASSWORD` | `admin` | Пароль сервиса auth |
| `DATALENS_API_VERSION_DEFAULT` | `2` | Заголовок `x-dl-api-version` |
| `US_TENANT_ID` | `common` | OSS single-tenant |

Хосты `http://us:8080` работают **только** если контейнер в той же docker-сети, что DataLens.

## datalens-mcp

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `MCP_AUTH_TOKEN` | — | Bearer MCP-клиентов (обязателен) |
| `DL_API_TOKEN` | — | Тот же, что у API; MCP ходит в API как сервис |
| `DATALENS_API_HOST` | `http://datalens-api:8393` | В compose подставляется с портом API |
| `DATALENS_API_VERSION` | `2` | `x-dl-api-version` на вызовах RPC |

Клиентский MCP-токен **не** пробрасывается в DataLens. Внутрь API всегда `DL_API_TOKEN` из env MCP.

# Установка

Нужен уже запущенный DataLens OSS 2.9.0. Этот репозиторий его compose не правит и свою сеть не создаёт: контейнеры входят в существующую docker-сеть.

## Сеть

```bash
docker network ls
```

Имя сети запишите в `DATALENS_NETWORK`. Часто это `datalens_default`. Если имя другое, а в `.env` оставлен образец, контейнер не резолвит `us`.

## Токены и логин

Из `.env` вашего DataLens:

- `US_MASTER_TOKEN` — master-token сервиса `us` (тот же, что у control-api).
- `AUTH_LOGIN` и `AUTH_PASSWORD` — учётка сервиса `auth`. На свежей установке часто `admin` / `admin`.

`DL_API_TOKEN` и `MCP_AUTH_TOKEN` задайте сами, разными строками. Образец в `env.example` — `change-me`, его в работе не оставляйте.

```bash
cp env.example .env
docker compose up -d --build
```

Команда без профилей поднимает только API и MCP. Ядро и прокси UI не стартуют и порт UI не занимают.

## Проверка

```bash
curl -sS http://127.0.0.1:8393/health
curl -sS http://127.0.0.1:8394/health
```

Порты по умолчанию: `DATALENS_API_PORT=8393`, `DATALENS_MCP_PORT=8394`.

## MCP

URL: `http://127.0.0.1:8394/mcp`

Заголовок: `Authorization: Bearer <MCP_AUTH_TOKEN>`

Транспорт — Streamable HTTP, `POST /mcp`.

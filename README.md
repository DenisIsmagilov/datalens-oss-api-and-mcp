# DataLens OSS API и MCP

Транслятор [облачного DataLens Public API](https://api.datalens.tech) для **open-source DataLens 2.9.0** и MCP-сервер (Streamable HTTP) над ним.

Не является официальным продуктом Yandex / [datalens-tech/datalens](https://github.com/datalens-tech/datalens). Лицензия — [MIT](LICENSE).

Проверено на DataLens OSS **v2.9.0** (compose: сервисы `us`, `auth`, `control-api`, `meta-manager`). Другие версии не обещаем.

## Что внутри

| Каталог | Назначение | Порт по умолчанию |
|---|---|---|
| `datalens-api/` | `POST /rpc/<method>` в формате облака → внутренние HTTP OSS | 8393 |
| `datalens-mcp/` | MCP tools → `datalens-api` | 8394 |

Нужен **уже запущенный** DataLens (официальный docker compose). Этот репозиторий **не** поднимает Postgres/US/UI и **не** правит ваш `docker-compose.yaml`. Контейнеры входят в существующую docker-сеть.

## Быстрый старт

```bash
git clone https://github.com/DenisIsmagilov/datalens-oss-api-and-mcp.git
cd datalens-oss-api-and-mcp
cp env.example .env
```

В `.env`:

1. `US_MASTER_TOKEN`, `AUTH_LOGIN`, `AUTH_PASSWORD` — из `.env` вашего DataLens (`AUTH_*` в OSS часто `admin` / `admin`, лучше сменить).
2. `DL_API_TOKEN` и `MCP_AUTH_TOKEN` — свои длинные случайные строки.
3. `DATALENS_NETWORK` — имя сети `docker network ls` (часто `datalens_default`, если каталог клона называется `datalens`).

```bash
docker compose up -d --build
```

Проверка:

```bash
curl -sS "http://127.0.0.1:8393/health"
curl -sS "http://127.0.0.1:8394/health"

curl -X POST "http://127.0.0.1:8393/rpc/getWorkbooksList" \
  -H "Authorization: Bearer ${DL_API_TOKEN}" \
  -H "x-dl-api-version: 2" \
  -H "Content-Type: application/json" \
  -d '{"page":0,"pageSize":10}'
```

MCP для Cursor: `http://127.0.0.1:8394/mcp`, заголовок `Authorization: Bearer <MCP_AUTH_TOKEN>`.

## Документация

- [Установка](docs/install.md)
- [Конфигурация](docs/configuration.md)
- [RPC API](docs/rpc-api.md)
- [MCP](docs/mcp.md)
- [Безопасность](docs/security.md)
- [Ошибки](docs/errors.md)

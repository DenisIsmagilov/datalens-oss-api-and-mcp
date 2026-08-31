# Установка на уже работающий DataLens

Нужен DataLens OSS **2.9.0**, запущенный через docker compose (сервисы `us`, `auth`, `control-api`, `meta-manager` в одной сети). Свой compose DataLens не меняйте.

## 1. Сеть

```bash
docker network ls
```

Ищите сеть вроде `datalens_default` (имя = `{каталог-проекта}_default`). Запишите его в `.env` как `DATALENS_NETWORK`. Если сеть другая, а в `.env` оставить дефолт — контейнеры не увидят `us` / `auth`.

## 2. Секреты

Из `.env` каталога DataLens перенесите:

| Переменная | Откуда |
|---|---|
| `US_MASTER_TOKEN` | тот же токен, что у сервиса `us` / `control-api` |
| `AUTH_LOGIN` / `AUTH_PASSWORD` | сервис `auth` (часто `admin` / `admin` на свежей установке) |

Задайте сами (не берите из примеров):

| Переменная | Смысл |
|---|---|
| `DL_API_TOKEN` | Bearer для клиентов `datalens-api` |
| `MCP_AUTH_TOKEN` | Bearer для MCP-клиентов; **другая** строка, не копия `DL_API_TOKEN` |

```bash
cp env.example .env
# отредактировать .env
docker compose up -d --build
```

## 3. Проверка

```bash
curl -sS "http://127.0.0.1:8393/health"
# {"status":"ok"}

curl -sS "http://127.0.0.1:8394/health"
# {"status":"ok"}

curl -X POST "http://127.0.0.1:8393/rpc/getWorkbooksList" \
  -H "Authorization: Bearer ${DL_API_TOKEN}" \
  -H "x-dl-api-version: 2" \
  -H "Content-Type: application/json" \
  -d '{"page":0,"pageSize":10}'
```

401 — неверный `DL_API_TOKEN`. Пустой/ошибка соединения с `us` — не та docker-сеть или DataLens не запущен.

## 4. Cursor

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

Если DataLens на другой машине — подставьте её хост вместо `127.0.0.1`, порт MCP не открывайте в интернет без firewall (см. [security.md](security.md)).

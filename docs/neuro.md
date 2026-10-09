# Ядро вопросов

Профиль `neuro` поднимает API, MCP и ядро. Порт ядра — `NEURO_PORT` (8396).

```bash
docker compose --profile neuro up -d --build
```

Пакет в образе — `default`, без чужого каталога. Канал: `POST /v1/chat`, токен `NEURO_API_TOKEN`.

## Справочник функций

Страниц справочника в git нет. Команда из корня репозитория:

```bash
sh datalens-neuro/scripts/fetch-formula-docs.sh
```

Она читает `formula-docs/SOURCE.md` и кладёт `*.md` в `datalens-neuro/formula-docs/`. Каталог смонтирован в контейнер как `/app/formula-docs`. После скрипта:

```bash
docker compose --profile neuro up -d --no-deps datalens-neuro
```

Пока страниц нет, ядро пишет в лог `formula docs have no fragments` и стартует. У исходного репозитория нет файла LICENSE, поэтому страницы не коммитятся.

## Запрос

Тело читается как `ChatRequest`: обязательное поле `message`, необязательное `pack`.

```bash
curl -sS http://127.0.0.1:8396/v1/chat \
  -H "Authorization: Bearer <NEURO_API_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"message":"Какие дашборды есть?","pack":"default"}'
```

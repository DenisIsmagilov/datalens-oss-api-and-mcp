# Кнопка на странице DataLens

Профиль `panel` поднимает ядро и прокси `datalens-neuro-panel`. Прокси публикует `DATALENS_UI_PORT` (по умолчанию 8080) и ходит в UI DataLens по `DATALENS_UI_UPSTREAM` (по умолчанию `http://ui:8080`). Скрипта, который правит чужой compose, нет: шаги ниже делаете вы.

Highcharts по-прежнему грузится из интернета. Прокси его не раздаёт и не переписывает: он только вставляет скрипт в HTML.

## Шаги

1. Остановить свой DataLens так, как вы обычно его останавливаете.
2. В сервисе `ui` убрать публикацию порта на хост (строка `ports` с портом UI, часто `8080`). В сети compose сервис остаётся доступен как `ui:8080`.
3. Запустить DataLens снова.
4. В `.env` этого репозитория выставить `NEURO_UI_ENABLED=true`. `NEURO_UI_ORIGINS` и `NEURO_PUBLIC_ORIGIN` поставить на тот хост, которым открывают UI. Origin UI — адрес страницы (часто `http://127.0.0.1:8080`). Origin ядра — тот же хост и порт `NEURO_PORT` (часто `http://127.0.0.1:8396`). Если сервис UI называется не `ui`, задайте `DATALENS_UI_UPSTREAM`.
5. Запустить профиль:

```bash
docker compose --profile panel up -d --build
```

Если порт `DATALENS_UI_PORT` занят, публикация `ui` ещё не снята.

В HTML перед `</head>` появляется скрипт, который задаёт `window.__DATALENS_NEURO_ORIGIN` и грузит `/ui/loader.js`.

## Откат

Вернуть `ports` у `ui` и остановить контейнер `datalens-neuro-panel`:

```bash
docker compose stop datalens-neuro-panel
```

После этого снова опубликуйте порт у `ui` и запустите DataLens, как раньше. API и MCP от отката не зависят.

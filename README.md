# DataLens OSS API, MCP и нейроаналитик

Транслятор облачного DataLens Public API для **open-source DataLens 2.9.0**, MCP-сервер над ним и необязательное ядро вопросов по дашборду.

Не является официальным продуктом Yandex / datalens-tech. Лицензия — [MIT](LICENSE).

Проверено на DataLens OSS **2.9.0**. Другие версии не обещаем.

## Быстрый старт (API и MCP)

Уже запущенный DataLens не правится.

```bash
git clone https://github.com/DenisIsmagilov/datalens-oss-api-and-mcp.git
cd datalens-oss-api-and-mcp
cp env.example .env
```

В `.env`: `US_MASTER_TOKEN`, `AUTH_LOGIN`, `AUTH_PASSWORD` из вашего DataLens. `DL_API_TOKEN` и `MCP_AUTH_TOKEN` задайте сами. Имя сети: `docker network ls`, переменная `DATALENS_NETWORK` (часто `datalens_default`).

```bash
docker compose up -d --build
curl -sS http://127.0.0.1:8393/health
curl -sS http://127.0.0.1:8394/health
```

Эта команда не поднимает ядро и не занимает порт UI.

## Необязательно

- Ядро вопросов: [docs/neuro.md](docs/neuro.md), профиль `neuro`.
- Кнопка на странице DataLens: [docs/panel.md](docs/panel.md), профиль `panel`. Highcharts по-прежнему грузится из интернета. Свой compose DataLens для кнопки правите вы, по этой инструкции.

Остальное: [установка](docs/install.md), [переменные](docs/configuration.md), [RPC](docs/rpc-api.md), [MCP](docs/mcp.md), [безопасность](docs/security.md), [ошибки](docs/errors.md).

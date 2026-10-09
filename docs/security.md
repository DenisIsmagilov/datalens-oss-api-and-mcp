# Безопасность

`DL_API_TOKEN`, `MCP_AUTH_TOKEN` и `NEURO_API_TOKEN` равны правам сервисного пользователя DataLens: через них доступно то, что умеет API от этой учётки. Это не разграничение по пользователям UI.

- `MCP_AUTH_TOKEN`, `DL_API_TOKEN` и `NEURO_API_TOKEN` — разные строки. Образец `change-me` замените до запуска.
- Порты API (`8393`), MCP (`8394`) и ядра (`NEURO_PORT`, по умолчанию `8396`) не выставляйте в интернет без firewall.
- Cookie панели (`auth` DataLens) уходит на тот же хост, что и UI, на порт `NEURO_PORT`. `NEURO_PUBLIC_ORIGIN` должен быть этим хостом и этим портом. Другое имя хоста cookie не получит.
- `AUTH_TOKEN_PUBLIC_KEY` в репозиторий не класть. В `env.example` поле пустое: ключ копируете из своего `datalens-auth` только в локальный `.env`.

Файл `.env` не коммитится.

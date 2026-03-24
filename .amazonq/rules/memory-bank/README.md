# MEMORY — системная память протоколов

Точка входа: **INDEX.md**

Контекст для агентов и операторов задаётся в:
- `.cursor/rules/memory.mdc` (всегда применяется в Cursor)
- `AGENTS.md` в корне tools
- `paths.py`: `MEMORY_DIR`, `get_memory_path()`

В коде: `MEMORY_DIR` доступен в `C3_server/server.py`, `linehackserv_file/config/config.py`, `minerdeploy_file/config/settings.py`.

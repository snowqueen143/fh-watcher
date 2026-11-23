# Freelancehunt watcher

Каждые ~10 минут проверяет новые проекты на Freelancehunt (Python, боты, парсинг, обработка данных)
и присылает подходящие в Telegram вместе с готовым текстом отклика. Работает бесплатно на GitHub Actions.

- спам-рассылки, сбор чужих контактов и чужие стеки (WordPress, 1С, мобилки) отфильтрованы — `EXCLUDE` в `watcher.py`
- отклик подстраивается под тип задачи (бот / парсер / таблицы / правка / Python) и язык проекта (RU/UA) — `bids.py`
- цена в отклике — ~80% бюджета заказчика, если он указан

## Проверка без отправки

```
python watcher.py --dry
```

## Запуск на GitHub (бесплатно)

1. Создать **публичный** репозиторий на github.com и загрузить в него эти файлы (вместе с папкой `.github`).
2. Settings → Secrets and variables → Actions → **New repository secret**:
   - `BOT_TOKEN` — токен бота от @BotFather
   - `TG_CHAT_ID` — необязательно, найдётся сам, если написать боту /start
3. Actions → watch-freelancehunt → **Run workflow** — первый запуск пришлёт «✅ Слежу за Freelancehunt».

Токен лежит только в секретах GitHub, в коде его нет.

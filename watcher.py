"""Проверяет новые проекты на Freelancehunt и шлёт их в Telegram с готовым откликом.

Запуск:  python watcher.py          — проверить и отправить
         python watcher.py --dry    — только показать в консоли, ничего не отправлять
Переменные окружения: BOT_TOKEN (обязательно), TG_CHAT_ID (необязательно — найдётся сам).
"""

import html
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

from bids import make_bid

# Python, Bot Development, Data Parsing, Data Processing
SKILL_IDS = "22,180,169,178"
API = "https://api.freelancehunt.com/v2/projects"
STATE_FILE = Path(__file__).with_name("state.json")

# Проекты, которые нам не подходят
EXCLUDE = re.compile(
    r"wordpress|1с|1c|bitrix|битрикс|ios|android|swift|kotlin|flutter|unity|"
    r"голосов|voice|дзвін|звонк|php на python|перенос backend|blockchain|крипт|solidity|"
    r"монтаж|starlink|"
    # спам-рассылки и сбор чужих персональных данных — не берём
    r"розсил|рассыл|масов|массов|спам|spam|инвайт|інвайт|invite|"
    r"(?:аудитор|підписник|подписчик|facebook|фейсбук|instagram|інстаграм|инстаграм|инстпграм)"
    r".{0,250}(?:email|e-mail|маил|мейл|пошт|почт|телефон|phone)",
    re.I | re.S,
)
# Признаки «нашего» проекта — за них ставим ⭐
GOOD = re.compile(r"telegram|телеграм|бот|bot|парс|scrap|python|скрипт|google sheets|таблиц|автоматиз", re.I)

MAX_TG_LEN = 4000


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"seen": [], "chat_id": None}


def save_state(state: dict) -> None:
    state["seen"] = state["seen"][-500:]
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def fetch_projects() -> list[dict]:
    r = httpx.get(API, params={"filter[skill_id]": SKILL_IDS}, timeout=30,
                  headers={"Accept-Language": "ru"})
    r.raise_for_status()
    return r.json()["data"]


def age_text(published: str) -> str:
    dt = datetime.fromisoformat(published)
    minutes = int((datetime.now(timezone.utc) - dt).total_seconds() // 60)
    if minutes < 60:
        return f"{minutes} мин назад"
    if minutes < 60 * 24:
        return f"{minutes // 60} ч назад"
    return f"{minutes // 1440} дн назад"


def format_message(p: dict) -> str:
    a = p["attributes"]
    name, desc = a["name"], (a.get("description") or "").strip()
    budget = a.get("budget")
    kind, bid = make_bid(name, desc, budget)
    star = "⭐ " if GOOD.search(f"{name} {desc}") else ""
    budget_txt = f"{budget['amount']} {budget['currency']}" if budget else "не указан"
    employer = a.get("employer") or {}
    emp_txt = f"{employer.get('login', '?')}, проектов: {employer.get('completed_projects', 0)}"
    url = p["links"]["self"]["web"]

    head = (
        f"{star}<b>{html.escape(name)}</b>\n"
        f"💰 {budget_txt} · 🕐 {age_text(a['published_at'])} · 🙋 ставок: {a.get('bid_count', 0)}\n"
        f"🏷 {', '.join(s['name'] for s in a['skills'])}\n"
        f"👤 {html.escape(emp_txt)}\n"
        f"🔗 {url}\n\n"
    )
    tail = f"\n\n✍️ <b>Готовый отклик</b> (нажми, чтобы скопировать):\n<pre>{html.escape(bid)}</pre>"
    room = MAX_TG_LEN - len(head) - len(tail) - 20
    short_desc = desc if len(desc) <= min(room, 700) else desc[: min(room, 700)].rstrip() + "…"
    return head + html.escape(short_desc) + tail


def find_chat_id(token: str) -> int | None:
    r = httpx.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=30)
    for upd in r.json().get("result", []):
        msg = upd.get("message") or {}
        chat = msg.get("chat") or {}
        if chat.get("type") == "private":
            return chat["id"]
    print("getUpdates:", r.status_code, r.text[:200])
    return None


def send(token: str, chat_id: int, text: str) -> None:
    r = httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
        timeout=30,
    )
    if not r.json().get("ok"):
        raise RuntimeError(f"Telegram: {r.status_code} {r.text[:300]}")


def main() -> None:
    dry = "--dry" in sys.argv
    state = load_state()
    projects = fetch_projects()
    first_run = not state["seen"]
    new = [p for p in projects if p["id"] not in state["seen"]]
    fresh = [p for p in new if not EXCLUDE.search(p["attributes"]["name"] + " " + (p["attributes"].get("description") or ""))]
    print(f"Проектов: {len(projects)}, новых: {len(new)}, подходящих: {len(fresh)}, первый запуск: {first_run}")

    if dry:
        for p in fresh:
            print("=" * 60)
            print(format_message(p))
        return

    token = os.environ["BOT_TOKEN"]
    chat_id = os.environ.get("TG_CHAT_ID") or state.get("chat_id") or find_chat_id(token)
    if not chat_id:
        print("Не знаю, кому слать: напишите боту /start и запустите снова.")
        sys.exit(1)
    state["chat_id"] = int(chat_id)

    if first_run:
        send(token, chat_id, f"✅ Слежу за Freelancehunt (Python, боты, парсинг). Сейчас открыто проектов: {len(projects)}. "
                             "Буду присылать новые с готовым откликом.")
    else:
        for p in sorted(fresh, key=lambda x: x["attributes"]["published_at"]):
            send(token, chat_id, format_message(p))

    state["seen"].extend(p["id"] for p in new)
    save_state(state)


if __name__ == "__main__":
    main()

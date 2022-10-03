from random import choice
import os
import base64
import json
import time

import telegram
from dotenv import load_dotenv
from playwright.sync_api import (
    Playwright,
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)

LAST_UPDATE_HASH_FILE = "last_update_hash.json"

PW_PAGE_TIMEOUT = 60000
PW_DESKTOP_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:105.0) Gecko/20100101 Firefox/105.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:101.0) Gecko/20100101 Firefox/101.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.100 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.14; rv:71.0) Gecko/20100101 Firefox/71.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.1.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:65.0) Gecko/20100101 Firefox/65.0",
]


def random_ua() -> str:
    return choice(PW_DESKTOP_AGENTS)


def new_update(latest_hash, all_hashes) -> bool:
    try:
        with open(LAST_UPDATE_HASH_FILE, encoding="utf-8") as file:
            seen = json.load(file)["data"]
    except FileNotFoundError:
        seen = json.dumps({"data": []}, indent=4)
        with open(LAST_UPDATE_HASH_FILE, "w", encoding="utf-8") as file:
            file.write(seen)

    if latest_hash in seen:
        print("│       ├── No updates detected")
        return False

    with open(LAST_UPDATE_HASH_FILE, "w", encoding="utf-8") as file:
        seen_data = json.loads(seen)["data"]
        file.write(json.dumps({"data": list(set(all_hashes + seen_data))}, indent=4))
        return True


def telegram_msg(args):
    for arg in args:
        subject = arg.get("subject", "")
        content = arg["content"]
        url = arg["url"]
        timestamp = time.strftime("%d-%m-%Y", time.localtime())

        bot.sendMessage(
            os.getenv("TELEGRAM_CHANNEL_ID"),
            text=f"""
<strong><u>📣 [{timestamp}]: {subject}</u></strong>
{content}

<i><a href="{url}">להודעה המקורית באתר רכבת ישראל</a></i>🚂
        """,
            parse_mode=telegram.ParseMode.HTML,
            disable_web_page_preview=True,
        )


def run(playwright: Playwright) -> None:  # pylint: disable=redefined-outer-name
    browser_ua = random_ua()
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(user_agent=browser_ua)

    print("│   └── New context")
    print(f"│       ├── UserAgent: {browser_ua}")

    page = context.new_page()
    try:
        page.goto(
            "https://www.rail.co.il/updates",
            wait_until="networkidle",
            timeout=PW_PAGE_TIMEOUT,
        )
    except PlaywrightTimeoutError:
        print(f"│       └── Timeout reached after {PW_PAGE_TIMEOUT / 1000}s")
        context.close()
        browser.close()
        return

    update_carrousel = page.locator("[id^='UpdateCarrousel']")
    updates = update_carrousel.locator("li")
    count = updates.count()

    if count:
        all_hashes = []
        latest_hash = base64.b64encode(updates.all_inner_texts()[0].encode()).decode()
        for entry in updates.all_inner_texts():
            all_hashes.append(base64.b64encode(entry.encode()).decode())

        is_new_update = new_update(latest_hash=latest_hash, all_hashes=all_hashes)

        if is_new_update:
            print("│       └── New entry detected")
            aggr_list = []
            for i in range(1):
                msg = {}

                subject = updates.nth(i).locator("h2").inner_text()
                more_details = updates.nth(i).locator("text=לפרטים נוספים")
                if more_details.is_visible():
                    more_details.click()
                    page.wait_for_load_state("networkidle")

                    msg.update(
                        subject=subject,
                        content=page.locator("div.contentPlace").inner_text(),
                    )
                else:
                    msg.update(content=updates.nth(i).inner_text())

                msg.update(url=page.url)
                aggr_list.append(msg)

                page.go_back()

            telegram_msg(aggr_list)
            print("│       │   └── Telegram message sent")

        context.close()
        browser.close()
        print("│       └── Context closed")


if __name__ == "__main__":
    load_dotenv()

    if os.getenv("TIME_INTERVAL") is None:
        raise RuntimeError("'TIME_INTERVAL' env is not set.")

    if os.getenv("TELEGRAM_CHANNEL_ID") is None:
        raise RuntimeError("'TELEGRAM_CHANNEL_ID' env is not set.")

    if os.getenv("TELEGRAM_TOKEN") is None:
        raise RuntimeError("'TELEGRAM_TOKEN' env is not set.")

    bot = telegram.Bot(token=os.getenv("TELEGRAM_TOKEN"))

    starttime = time.time()
    while True:
        print(
            f"├── {time.strftime('%d-%m-%Y %H:%M:%S %Z', time.localtime(time.time()))}"
        )
        with sync_playwright() as playwright:
            run(playwright)
        time.sleep(
            int(os.getenv("TIME_INTERVAL"))
            - ((time.time() - starttime) % int(os.getenv("TIME_INTERVAL")))
        )

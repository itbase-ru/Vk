#!/usr/bin/env python3
"""Автопостинг мемов из папки в сообщество ВКонтакте.

Как это работает:
  * картинки лежат в папке memes/ (jpg, jpeg, png)
  * по желанию рядом с картинкой можно положить .txt с таким же именем,
    его текст станет подписью (meme1.jpg -> meme1.txt)
  * к каждому посту автоматически добавляются хэштеги из hashtags.txt
  * после публикации картинка переезжает в папку posted/

Запуск:
  python post_meme.py                     # опубликовать 1 мем сейчас
  python post_meme.py --count 20 --every-hours 6
                                          # поставить 20 мемов в отложенные,
                                          # по одному каждые 6 часов

Нужны переменные окружения:
  VK_TOKEN     - ключ доступа сообщества (права: стена, фотографии)
  VK_GROUP_ID  - номер сообщества (только цифры)
"""
import argparse
import os
import shutil
import sys
import time
from pathlib import Path

import requests

API = "https://api.vk.com/method/"
API_VERSION = "5.199"
IMAGE_EXT = {".jpg", ".jpeg", ".png"}

BASE = Path(__file__).resolve().parent
MEMES_DIR = BASE / "memes"
POSTED_DIR = BASE / "posted"
HASHTAGS_FILE = BASE / "hashtags.txt"


def vk(method, token, **params):
    """Вызов метода API ВК, при ошибке бросает исключение с текстом."""
    data = {**params, "access_token": token, "v": API_VERSION}
    resp = requests.post(API + method, data=data, timeout=60).json()
    if "error" in resp:
        err = resp["error"]
        raise RuntimeError(f"{method}: {err.get('error_code')} {err.get('error_msg')}")
    return resp["response"]


def upload_photo(token, group_id, path):
    """Загружает картинку на сервер ВК и возвращает строку вложения."""
    server = vk("photos.getWallUploadServer", token, group_id=group_id)
    with open(path, "rb") as f:
        up = requests.post(server["upload_url"], files={"photo": f}, timeout=120).json()
    saved = vk(
        "photos.saveWallPhoto",
        token,
        group_id=group_id,
        photo=up["photo"],
        server=up["server"],
        hash=up["hash"],
    )
    p = saved[0]
    return f"photo{p['owner_id']}_{p['id']}"


def read_hashtags():
    if not HASHTAGS_FILE.exists():
        return ""
    text = HASHTAGS_FILE.read_text(encoding="utf-8")
    return " ".join(text.split())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=1, help="сколько мемов опубликовать")
    parser.add_argument(
        "--every-hours",
        type=float,
        default=0,
        help="если больше 0, посты ставятся в отложенные с таким интервалом",
    )
    args = parser.parse_args()

    token = os.environ.get("VK_TOKEN")
    group = os.environ.get("VK_GROUP_ID")
    if not token or not group:
        sys.exit("Не заданы VK_TOKEN или VK_GROUP_ID")
    group_id = abs(int(group))

    MEMES_DIR.mkdir(exist_ok=True)
    POSTED_DIR.mkdir(exist_ok=True)

    files = sorted(p for p in MEMES_DIR.iterdir() if p.suffix.lower() in IMAGE_EXT)
    if not files:
        print("В папке memes/ нет картинок, публиковать нечего.")
        return

    hashtags = read_hashtags()
    now = int(time.time())

    for i, img in enumerate(files[: args.count]):
        caption_file = img.with_suffix(".txt")
        caption = ""
        if caption_file.exists():
            caption = caption_file.read_text(encoding="utf-8").strip()
        message = "\n\n".join(part for part in (caption, hashtags) if part)

        attachment = upload_photo(token, group_id, img)
        params = {
            "owner_id": -group_id,
            "from_group": 1,
            "message": message,
            "attachments": attachment,
        }
        if args.every_hours > 0:
            params["publish_date"] = now + int(args.every_hours * 3600 * (i + 1))

        vk("wall.post", token, **params)
        print(f"Готово: {img.name}")

        shutil.move(str(img), POSTED_DIR / img.name)
        if caption_file.exists():
            shutil.move(str(caption_file), POSTED_DIR / caption_file.name)
        time.sleep(1)


if __name__ == "__main__":
    main()

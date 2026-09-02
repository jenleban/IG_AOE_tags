#!/usr/bin/env python3
"""Sync recent public hashtag media into data/posts.json.

Hashtag posts publish automatically. IDs in data/removed-posts.json are
excluded so a removed post is not re-imported on the next sync.
"""
import hashlib
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

GRAPH_VERSION = os.environ.get("GRAPH_VERSION", "v26.0")
IG_USER_ID = os.environ.get("IG_USER_ID", "17841401832996914")
ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")
HASHTAGS = ["artofed", "artofedcommunity", "theartofed"]
DATA_PATH = Path("data/posts.json")
REMOVED_PATH = Path("data/removed-posts.json")

if not ACCESS_TOKEN:
    raise SystemExit("META_ACCESS_TOKEN is not set")


def graph_get(path, params):
    query = dict(params)
    query["access_token"] = ACCESS_TOKEN
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{path}?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(url, headers={"User-Agent": "AOE-Instagram-Gallery-Sync/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except Exception as exc:
        raise RuntimeError(f"Meta request failed for {path}: {exc}") from exc
    if "error" in payload:
        raise RuntimeError(f"Meta API error for {path}: {payload['error']}")
    return payload


def hashtag_id(hashtag):
    result = graph_get("ig_hashtag_search", {"user_id": IG_USER_ID, "q": hashtag})
    items = result.get("data", [])
    return str(items[0]["id"]) if items else None


def recent_media(hashtag_id_value):
    fields = "id,media_type,media_url,permalink,timestamp,caption"
    result = graph_get(
        f"{hashtag_id_value}/recent_media",
        {"user_id": IG_USER_ID, "fields": fields, "limit": "50"},
    )
    return result.get("data", [])


def accent_for(post_id):
    palette = ["#00AFD7", "#E44398", "#82C341", "#FFCE51", "#025A89"]
    digest = hashlib.sha256(str(post_id).encode()).digest()[0]
    return palette[digest % len(palette)]


def title_from_caption(caption):
    if not caption:
        return "A moment from the art education community"
    first_line = " ".join(caption.strip().splitlines()).strip()
    return first_line[:78] + ("…" if len(first_line) > 78 else "")


def normalize(post, hashtag):
    caption = (post.get("caption") or "").strip()
    media_url = post.get("media_url") or ""
    permalink = post.get("permalink") or "https://www.instagram.com/theartofed/"
    return {
        "id": post.get("id"),
        "image": media_url,
        "alt": caption[:180] or "Public Instagram post from the art education community",
        "source": "Instagram community post",
        "label": f"#{hashtag}",
        "hashtags": [f"#{hashtag}"],
        "title": title_from_caption(caption),
        "excerpt": caption[:220] or "Shared by the art education community.",
        "accent": accent_for(post.get("id")),
        "featured": False,
        "media_type": post.get("media_type", "IMAGE"),
        "permalink": permalink,
        "timestamp": post.get("timestamp"),
    }


def load_removed_ids():
    if not REMOVED_PATH.exists():
        return set()
    data = json.loads(REMOVED_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{REMOVED_PATH} must contain a JSON array")
    return {str(value) for value in data}


def post_identifiers(post):
    return {
        str(value)
        for value in (post.get("id"), post.get("instagram_media_id"))
        if value is not None
    }


def is_removed(post, removed_ids):
    return bool(post_identifiers(post) & removed_ids)


def merge_posts(existing, incoming, removed_ids):
    existing = [
        post for post in existing
        if post.get("id") is not None and not is_removed(post, removed_ids)
    ]
    incoming = [
        post for post in incoming
        if post.get("id") is not None and not is_removed(post, removed_ids)
    ]

    by_id = {str(post["id"]): post for post in existing}
    for post in incoming:
        key = str(post["id"])
        if key in by_id:
            current = by_id[key]
            current["hashtags"] = sorted(set(current.get("hashtags", []) + post.get("hashtags", [])))
            current["label"] = current["hashtags"][0] if current["hashtags"] else post["label"]
            current["permalink"] = post.get("permalink") or current.get("permalink")
            current["timestamp"] = post.get("timestamp") or current.get("timestamp")
        else:
            by_id[key] = post

    live_posts = [post for post in by_id.values() if post.get("source") != "Sample classroom post"]
    sample_posts = [post for post in by_id.values() if post.get("source") == "Sample classroom post"]

    # Keep sample artwork visible only when no live community posts are available.
    if not live_posts:
        return sample_posts

    live_posts.sort(key=lambda post: post.get("timestamp") or "", reverse=True)
    return live_posts[:200]


existing = json.loads(DATA_PATH.read_text(encoding="utf-8")) if DATA_PATH.exists() else []
removed_ids = load_removed_ids()
incoming = []

for hashtag in HASHTAGS:
    hid = hashtag_id(hashtag)
    if not hid:
        print(f"No hashtag ID returned for #{hashtag}")
        continue
    media = recent_media(hid)
    print(f"#{hashtag}: {len(media)} recent posts")
    incoming.extend(normalize(post, hashtag) for post in media)

merged = merge_posts(existing, incoming, removed_ids)
DATA_PATH.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"Wrote {len(merged)} posts to {DATA_PATH}")
print(f"Excluded {len(removed_ids)} removed post IDs")

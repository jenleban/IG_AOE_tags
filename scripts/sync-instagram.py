#!/usr/bin/env python3
"""Sync recent public hashtag media into data/posts.json.

This script is designed to run from GitHub Actions. It deliberately does not
handle Instagram mention webhooks. Those require a separately hosted endpoint.
"""
import hashlib
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

GRAPH_VERSION = os.environ.get("GRAPH_VERSION", "v26.0")
IG_USER_ID = os.environ.get("IG_USER_ID", "17841401832996914")
ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")
HASHTAGS = ["artofed", "artofedcommunity", "theartofed"]
DATA_PATH = Path("data/posts.json")

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


def merge_posts(existing, incoming):
    by_id = {str(post.get("id")): post for post in existing if post.get("id") is not None}
    for post in incoming:
        key = str(post.get("id"))
        if key in by_id:
            current = by_id[key]
            current["hashtags"] = sorted(set(current.get("hashtags", []) + post.get("hashtags", [])))
            current["label"] = current["hashtags"][0] if current["hashtags"] else post["label"]
        else:
            by_id[key] = post

    live_posts = [post for post in by_id.values() if post.get("source") != "Sample classroom post"]
    sample_posts = [post for post in existing if post.get("source") == "Sample classroom post"]

    # Keep the visual prototype visible if the target hashtags currently have no recent posts.
    if not live_posts:
        return existing

    combined = live_posts
    combined.sort(key=lambda post: post.get("timestamp") or "", reverse=True)
    return combined[:200]


existing = json.loads(DATA_PATH.read_text()) if DATA_PATH.exists() else []
incoming = []
for hashtag in HASHTAGS:
    hid = hashtag_id(hashtag)
    if not hid:
        print(f"No hashtag ID returned for #{hashtag}")
        continue
    media = recent_media(hid)
    print(f"#{hashtag}: {len(media)} recent posts")
    incoming.extend(normalize(post, hashtag) for post in media)

merged = merge_posts(existing, incoming)
DATA_PATH.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n")
print(f"Wrote {len(merged)} posts to {DATA_PATH}")

#!/usr/bin/env python3
"""Collect recent public hashtag posts for manual review.

Hashtag results are written to data/pending-posts.json instead of being
published directly to data/posts.json. Existing approved posts remain live.
Instagram @theartofed webhook posts are handled separately by Cloudflare.
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

HASHTAGS = [
    "artofed",
    "artofedcommunity",
    "theartofed",
]

POSTS_PATH = Path("data/posts.json")
PENDING_PATH = Path("data/pending-posts.json")
MAX_PENDING_POSTS = 200

if not ACCESS_TOKEN:
    raise SystemExit("META_ACCESS_TOKEN is not set")


def graph_get(path, params):
    query = dict(params)
    query["access_token"] = ACCESS_TOKEN

    url = (
        f"https://graph.facebook.com/{GRAPH_VERSION}/{path}?"
        f"{urllib.parse.urlencode(query)}"
    )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "AOE-Instagram-Gallery-Sync/1.0",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except Exception as exc:
        raise RuntimeError(
            f"Meta request failed for {path}: {exc}"
        ) from exc

    if "error" in payload:
        raise RuntimeError(
            f"Meta API error for {path}: {payload['error']}"
        )

    return payload


def hashtag_id(hashtag):
    result = graph_get(
        "ig_hashtag_search",
        {
            "user_id": IG_USER_ID,
            "q": hashtag,
        },
    )

    items = result.get("data", [])
    return str(items[0]["id"]) if items else None


def recent_media(hashtag_id_value):
    fields = "id,media_type,media_url,permalink,timestamp,caption"

    result = graph_get(
        f"{hashtag_id_value}/recent_media",
        {
            "user_id": IG_USER_ID,
            "fields": fields,
            "limit": "50",
        },
    )

    return result.get("data", [])


def accent_for(post_id):
    palette = [
        "#00AFD7",
        "#E44398",
        "#82C341",
        "#FFCE51",
        "#025A89",
    ]

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
    permalink = (
        post.get("permalink")
        or "https://www.instagram.com/theartofed/"
    )

    return {
        "id": post.get("id"),
        "image": media_url,
        "alt": (
            caption[:180]
            or "Public Instagram post from the art education community"
        ),
        "source": "Instagram hashtag candidate",
        "label": f"#{hashtag}",
        "hashtags": [f"#{hashtag}"],
        "title": title_from_caption(caption),
        "excerpt": (
            caption[:220]
            or "Shared by the art education community."
        ),
        "accent": accent_for(post.get("id")),
        "featured": False,
        "media_type": post.get("media_type", "IMAGE"),
        "permalink": permalink,
        "timestamp": post.get("timestamp"),
        "status": "pending",
    }


def load_json(path, fallback):
    if not path.exists():
        return fallback

    return json.loads(path.read_text(encoding="utf-8"))


def merge_pending(existing_posts, existing_pending, incoming):
    approved_ids = {
        str(post.get("id"))
        for post in existing_posts
        if post.get("id") is not None
    }

    pending_by_id = {
        str(post.get("id")): post
        for post in existing_pending
        if post.get("id") is not None
    }

    for post in incoming:
        post_id = post.get("id")

        if post_id is None or str(post_id) in approved_ids:
            continue

        key = str(post_id)

        if key in pending_by_id:
            current = pending_by_id[key]

            current["hashtags"] = sorted(
                set(
                    current.get("hashtags", [])
                    + post.get("hashtags", [])
                )
            )

            current["status"] = "pending"
        else:
            pending_by_id[key] = post

    pending = list(pending_by_id.values())

    pending.sort(
        key=lambda post: post.get("timestamp") or "",
        reverse=True,
    )

    return pending[:MAX_PENDING_POSTS]


existing_posts = load_json(POSTS_PATH, [])
existing_pending = load_json(PENDING_PATH, [])
incoming = []

for hashtag in HASHTAGS:
    hashtag_value = hashtag_id(hashtag)

    if not hashtag_value:
        print(f"No hashtag ID returned for #{hashtag}")
        continue

    media = recent_media(hashtag_value)
    print(f"#{hashtag}: {len(media)} recent posts")

    incoming.extend(
        normalize(post, hashtag)
        for post in media
    )

pending = merge_pending(
    existing_posts,
    existing_pending,
    incoming,
)

PENDING_PATH.write_text(
    json.dumps(
        pending,
        indent=2,
        ensure_ascii=False,
    ) + "\n",
    encoding="utf-8",
)

print(
    f"Wrote {len(pending)} pending posts to {PENDING_PATH}"
)

print(
    f"Kept {len(existing_posts)} approved/live posts in {POSTS_PATH}"
)

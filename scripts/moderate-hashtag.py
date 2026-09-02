#!/usr/bin/env python3

import json
import sys
from pathlib import Path

POSTS_PATH = Path("data/posts.json")
PENDING_PATH = Path("data/pending-posts.json")
MAX_POSTS = 200


def load_json(path):
    if not path.exists():
        return []

    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, data):
    path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )


if len(sys.argv) != 3:
    raise SystemExit(
        "Usage: moderate-hashtag.py POST_ID approve|reject"
    )


post_id = str(sys.argv[1])
decision = sys.argv[2].lower()

if decision not in {"approve", "reject"}:
    raise SystemExit("Decision must be approve or reject")

posts = load_json(POSTS_PATH)
pending = load_json(PENDING_PATH)

match = None
remaining_pending = []

for post in pending:
    if str(post.get("id")) == post_id:
        match = post
    else:
        remaining_pending.append(post)

if match is None:
    raise SystemExit(
        f"No pending hashtag post found with ID {post_id}"
    )

if decision == "approve":
    match.pop("status", None)
    match["source"] = "Instagram community post"

    existing_ids = {
        str(post.get("id"))
        for post in posts
        if post.get("id") is not None
    }

    if str(match.get("id")) not in existing_ids:
        posts.insert(0, match)

    posts = posts[:MAX_POSTS]
    save_json(POSTS_PATH, posts)
    print(f"Approved hashtag post {post_id}.")

else:
    print(f"Rejected hashtag post {post_id}.")

save_json(PENDING_PATH, remaining_pending)

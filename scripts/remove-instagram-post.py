#!/usr/bin/env python3
"""Remove a published Instagram post and block it from future hashtag syncs."""
import json
import sys
from pathlib import Path

POSTS_PATH = Path("data/posts.json")
REMOVED_PATH = Path("data/removed-posts.json")


def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if len(sys.argv) != 2:
    raise SystemExit("Usage: remove-instagram-post.py POST_ID")

post_id = str(sys.argv[1]).strip()
if not post_id:
    raise SystemExit("POST_ID cannot be empty")

posts = load_json(POSTS_PATH, [])
removed_ids = {str(value) for value in load_json(REMOVED_PATH, [])}

if post_id in removed_ids:
    print(f"Post {post_id} is already blocked and removed.")
    raise SystemExit(0)

def matches(post):
    return any(
        str(post.get(field)) == post_id
        for field in ("id", "instagram_media_id")
        if post.get(field) is not None
    )


matching = [post for post in posts if matches(post)]
if not matching:
    raise SystemExit(f"No published gallery post found with ID {post_id}")

remaining = [post for post in posts if not matches(post)]
for post in matching:
    for field in ("id", "instagram_media_id"):
        if post.get(field) is not None:
            removed_ids.add(str(post[field]))

save_json(POSTS_PATH, remaining)
save_json(REMOVED_PATH, sorted(removed_ids))
print(f"Removed post {post_id} from the gallery.")
print(f"Blocked {post_id} from future hashtag syncs.")

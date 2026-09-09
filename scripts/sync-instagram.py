#!/usr/bin/env python3
"""Sync Instagram posts and cache their images locally in the repository.

Instagram media URLs are temporary CDN URLs. This script keeps the original
URL for reference, downloads a stable local copy into assets/instagram/, and
stores that local path in the post's image field.
"""
import hashlib
import json
import mimetypes
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

GRAPH_VERSION = os.environ.get("GRAPH_VERSION", "v26.0")
IG_USER_ID = os.environ.get("IG_USER_ID", "17841401832996914")
ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")
HASHTAGS = ["artofed", "artofedcommunity", "theartofed"]
DATA_PATH = Path("data/posts.json")
REMOVED_PATH = Path("data/removed-posts.json")
IMAGE_DIR = Path("assets/instagram")
MAX_IMAGE_BYTES = 25 * 1024 * 1024

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


def download_image(url, destination):
    request = urllib.request.Request(url, headers={"User-Agent": "AOE-Instagram-Gallery-Sync/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        content_type = response.headers.get_content_type()
        data = response.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise RuntimeError(f"image exceeds {MAX_IMAGE_BYTES // (1024 * 1024)} MB")
    destination.write_bytes(data)
    return content_type


def extension_for(content_type, url):
    extensions = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    if content_type in extensions:
        return extensions[content_type]
    guessed = Path(urllib.parse.urlparse(url).path).suffix.lower()
    return guessed if guessed in {".jpg", ".jpeg", ".png", ".webp", ".gif"} else ".jpg"


def safe_id(post):
    value = str(post.get("instagram_media_id") or post.get("id") or "unknown")
    return re.sub(r"[^A-Za-z0-9._-]", "_", value)


def media_id_for(post):
    return str(post.get("instagram_media_id") or post.get("id") or "")


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


def refresh_mentioned_media_source(post):
    """Refresh a caption-mention through Meta's supported mentioned_media expansion.

    A direct GET /<media-id> is not reliable for media owned by other accounts.
    Hashtag media also cannot be refreshed after the 24-hour recent_media window.
    """
    media_id = media_id_for(post)
    if not media_id or post.get("source") != "Instagram mention":
        return None

    fields = f"mentioned_media.media_id({media_id}){{id,media_type,media_url,thumbnail_url,permalink,caption}}"
    try:
        payload = graph_get(IG_USER_ID, {"fields": fields})
    except Exception as exc:
        print(f"Could not refresh mention media URL for {media_id}: {exc}")
        return None

    items = (payload.get("mentioned_media") or {}).get("data", [])
    if not items:
        print(f"Meta returned no refreshable mention media for {media_id}")
        return None

    refreshed = items[0]
    media_type = refreshed.get("media_type") or post.get("media_type")
    url = refreshed.get("thumbnail_url") if media_type == "VIDEO" else refreshed.get("media_url")
    url = url or refreshed.get("media_url") or refreshed.get("thumbnail_url")
    if url:
        post["media_type"] = media_type or post.get("media_type", "IMAGE")
        return url
    return None


def cache_post_image(post):
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    identifier = safe_id(post)
    existing_local = sorted(IMAGE_DIR.glob(f"{identifier}.*"))
    current_image = str(post.get("image") or "")

    if current_image.startswith("assets/instagram/") and Path(current_image).exists():
        return True
    if existing_local:
        post["image"] = existing_local[0].as_posix()
        return True

    source_url = post.get("source_image_url") or (current_image if current_image.startswith("http") else "")
    candidate_urls = []
    if source_url:
        candidate_urls.append(source_url)

    # Meta supports a specific refresh path for caption mentions. Hashtag
    # media outside the 24-hour recent_media window cannot be rehydrated here.
    refreshed_url = refresh_mentioned_media_source(post)
    if refreshed_url and refreshed_url not in candidate_urls:
        candidate_urls.insert(0, refreshed_url)

    for url in candidate_urls:
        try:
            temporary = IMAGE_DIR / f".{identifier}.download"
            content_type = download_image(url, temporary)
            extension = extension_for(content_type, url)
            destination = IMAGE_DIR / f"{identifier}{extension}"
            temporary.replace(destination)
            post["image"] = destination.as_posix()
            post["source_image_url"] = url
            print(f"Cached {media_id_for(post)} -> {destination}")
            return True
        except Exception as exc:
            print(f"Could not cache {media_id_for(post)} from {url}: {exc}")
            temporary = IMAGE_DIR / f".{identifier}.download"
            if temporary.exists():
                temporary.unlink()

    print(f"WARNING: no stable image available for {media_id_for(post)}")
    return False


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
        "source_image_url": media_url,
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
    cleaned_existing = []
    for post in existing:
        if post.get("id") is None or is_removed(post, removed_ids):
            continue
        if not post.get("source_image_url") and str(post.get("image", "")).startswith("http"):
            post["source_image_url"] = post["image"]
        cleaned_existing.append(post)

    incoming = [post for post in incoming if post.get("id") is not None and not is_removed(post, removed_ids)]
    by_id = {str(post["id"]): post for post in cleaned_existing}

    for post in incoming:
        key = str(post["id"])
        if key in by_id:
            current = by_id[key]
            current["hashtags"] = sorted(set(current.get("hashtags", []) + post.get("hashtags", [])))
            current["label"] = current["hashtags"][0] if current["hashtags"] else post["label"]
            current["permalink"] = post.get("permalink") or current.get("permalink")
            current["timestamp"] = post.get("timestamp") or current.get("timestamp")
            if post.get("source_image_url"):
                current["source_image_url"] = post["source_image_url"]
        else:
            by_id[key] = post

    live_posts = [post for post in by_id.values() if post.get("source") != "Sample classroom post"]
    sample_posts = [post for post in by_id.values() if post.get("source") == "Sample classroom post"]
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

posts = merge_posts(existing, incoming, removed_ids)
cache_successes = 0
for post in posts:
    if cache_post_image(post):
        cache_successes += 1

DATA_PATH.write_text(json.dumps(posts, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"Wrote {len(posts)} posts to {DATA_PATH}")
print(f"Cached or confirmed {cache_successes} stable images")
print(f"Excluded {len(removed_ids)} removed post IDs")

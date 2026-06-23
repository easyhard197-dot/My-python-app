"""
InstaFetcher X — backend API
-----------------------------
Takes an Instagram reel/post URL and returns a direct video + thumbnail URL.
Built to be deployed as a Vercel Python serverless function.

Response shape matches what the existing index.html frontend expects:
  { "status": "success", "video": "...", "thumbnail": "..." }
  { "status": "error", "message": "..." }
"""

from flask import Flask, request, jsonify
import yt_dlp

app = Flask(__name__)


@app.after_request
def add_cors_headers(response):
    # Allow the frontend (hosted anywhere) to call this API from the browser
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


def extract_instagram_media(url: str):
    """Use yt-dlp to pull the direct video + thumbnail URL from an Instagram link."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "format": "best",
        "noplaylist": True,
        # Pretend to be a normal browser — helps avoid some basic blocks
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        },
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    # If it's a carousel/playlist, yt-dlp returns "entries" — grab the first video
    if info.get("entries"):
        info = info["entries"][0]

    video_url = info.get("url")

    # Fallback: pick the highest-resolution format manually
    if not video_url and info.get("formats"):
        playable = [f for f in info["formats"] if f.get("url")]
        if playable:
            best = max(playable, key=lambda f: f.get("height") or 0)
            video_url = best.get("url")

    thumbnail = info.get("thumbnail")

    return video_url, thumbnail


@app.route("/", methods=["GET", "OPTIONS"])
@app.route("/api/index", methods=["GET", "OPTIONS"])
def fetch():
    if request.method == "OPTIONS":
        # CORS preflight
        return "", 204

    url = (request.args.get("url") or "").strip()

    if not url:
        return jsonify({"status": "error", "message": "No URL provided."}), 400

    if "instagram.com" not in url:
        return jsonify({"status": "error", "message": "That doesn't look like an Instagram URL."}), 400

    try:
        video_url, thumbnail = extract_instagram_media(url)
    except Exception as e:
        # Most failures here = private post, deleted post, or Instagram blocking the request
        return jsonify({
            "status": "error",
            "message": "Could not fetch this post. It may be private, deleted, or Instagram is rate-limiting requests."
        }), 502

    if not video_url:
        return jsonify({
            "status": "error",
            "message": "This looks like a photo post or unsupported content — no video found."
        }), 404

    return jsonify({
        "status": "success",
        "video": video_url,
        "thumbnail": thumbnail,
    })


# Vercel's Python runtime auto-detects the "app" object as the WSGI handler.

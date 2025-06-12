import os
import time
from flask import Flask, request, jsonify
from supabase import create_client
from playwright.sync_api import sync_playwright

app = Flask(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route("/", methods=["GET"])
def home():
    return "✅ YouTube to MP3/MP4 API is running."

@app.route("/convert", methods=["POST"])
def convert():
    data = request.json
    url = data.get("video_url")
    fmt = data.get("format", "mp3")
    quality = data.get("quality", "720")

    if not url or fmt not in ["mp3", "mp4"]:
        return jsonify({"error": "Invalid request"}), 400

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            viewport={"width": 1280, "height": 800},
            device_scale_factor=1,
            is_mobile=False,
            has_touch=False,
            accept_downloads=True
        )
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        context.route("**/*", lambda route, request: (
            route.abort() if request.resource_type in ["image", "stylesheet", "font"] else route.continue_()
        ))
        page = context.new_page()
        page.goto("https://cnvmp3.com/v25", timeout=60000)

        if fmt == "mp4":
            page.click("#format-select-display")
            page.wait_for_selector('.format-select-options[data-format="0"]', timeout=5000)
            page.click('.format-select-options[data-format="0"]')
            page.fill("input#video-url", url)
            page.click("#quality-video-select-display")
            page.wait_for_selector(f'#quality-video-select-list-{quality}', timeout=5000)
            page.click(f'#quality-video-select-list-{quality}')
        else:
            page.fill("input#video-url", url)

        with page.expect_download() as download_info:
            page.click("input#convert-button-1")
            try:
                page.click("a#download-btn", timeout=1000)
            except:
                pass

        download = download_info.value
        download_url = download.url
        title = download.suggested_filename.rsplit(".", 1)[0]

        supabase.table("downloads").insert({
            "video_url": url,
            "format": fmt,
            "quality": quality if fmt == "mp4" else "N/A",
            "download_url": download_url,
            "title": title,
            "timestamp": int(time.time())
        }).execute()

        browser.close()
        return jsonify({"title": title, "download_url": download_url})

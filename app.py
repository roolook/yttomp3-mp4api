import os
import time
import requests
from urllib.parse import urlparse
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from supabase import create_client
from playwright.sync_api import sync_playwright

app = Flask(__name__)
CORS(app)

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print("⚠️ Supabase connection failed:", e)

# Ensure downloads directory exists
DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), 'downloads')
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

@app.route("/", methods=["GET"])
def home():
    return "✅ YouTube to MP3/MP4 API is running."

@app.route("/convert", methods=["POST"])
def convert():
    try:
        data = request.json
        url = data.get("video_url")
        fmt = data.get("format", "mp3")
        quality = data.get("quality", "720")

        if not url:
            return jsonify({"error": "Missing video_url parameter"}), 400
        if fmt not in ["mp3", "mp4"]:
            return jsonify({"error": "Invalid format, must be mp3 or mp4"}), 400

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
            page = context.new_page()
            
            try:
                page.goto("https://ytmp3.plus/en1/", timeout=60000)
                input_box = page.wait_for_selector("input[name='url']", timeout=10000)
                input_box.fill(url)
                page.click("button[type='submit']")
                page.wait_for_selector("a[href*='/download']", timeout=60000)
                download_link = page.query_selector("a[href*='/download']").get_attribute("href")
            except Exception as e:
                return jsonify({"error": f"Conversion failed: {str(e)}"}), 500
            finally:
                browser.close()

        # Generate filename and download
        filename = f"{int(time.time())}.{fmt}"
        file_path = os.path.join(DOWNLOAD_DIR, filename)

        try:
            with requests.get(download_link, stream=True) as r:
                r.raise_for_status()
                with open(file_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
        except Exception as e:
            if os.path.exists(file_path):
                os.remove(file_path)
            return jsonify({"error": f"Download failed: {str(e)}"}), 500

        download_url = f"{request.url_root}downloads/{filename}"
        return jsonify({
            "success": True,
            "download": download_url,
            "filename": filename
        })

    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500

@app.route('/downloads/<filename>', methods=['GET'])
def download_file(filename):
    try:
        return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)
    except FileNotFoundError:
        return jsonify({"error": "File not found"}), 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

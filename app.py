import os
import uuid
from flask import Flask, request, send_file, jsonify, render_template
import yt_dlp

app = Flask(__name__)

# Création du dossier si nécessaire
os.makedirs('downloads', exist_ok=True)

# En-têtes HTTP pour simuler un vrai navigateur
DEFAULT_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/122.0.0.0 Safari/537.36'
    )
}

# (Optionnel) Proxy pour Render si nécessaire
PROXY = os.getenv("PROXY")  # Exemple : http://user:pass@host:port

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/info', methods=['POST'])
def video_info():
    data = request.json
    url = data.get('url')

    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'http_headers': DEFAULT_HEADERS,
        'geo_bypass': True
    }

    if PROXY:
        ydl_opts['proxy'] = PROXY

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = [{
                'format_id': f['format_id'],
                'ext': f['ext'],
                'resolution': f.get('resolution') or f.get('height', ''),
                'format_note': f.get('format_note', ''),
                'filesize': f.get('filesize') or 0
            } for f in info.get('formats', []) if f.get('vcodec') != 'none' or f.get('acodec') != 'none']

            return jsonify({
                'title': info.get('title'),
                'thumbnail': info.get('thumbnail'),
                'duration': info.get('duration'),
                'formats': formats
            })

    except Exception as e:
        return jsonify({'error': f'Info extraction error: {str(e)}'}), 500

@app.route('/download', methods=['POST'])
def download_video():
    data = request.json
    url = data.get('url')
    format_id = data.get('format_id')

    if not url or not format_id:
        return jsonify({'error': 'Missing URL or format_id'}), 400

    filename = f"video_{uuid.uuid4().hex}.mp4"
    output_path = os.path.join("downloads", filename)

    ydl_opts = {
        'format': format_id,
        'outtmpl': output_path,
        'http_headers': DEFAULT_HEADERS,
        'geo_bypass': True,
        'concurrent_fragment_downloads': 1
    }

    if PROXY:
        ydl_opts['proxy'] = PROXY

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return send_file(output_path, as_attachment=True)
    except Exception as e:
        return jsonify({'error': f'Download error: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))

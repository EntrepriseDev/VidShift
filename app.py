import os
import uuid
import logging
import subprocess
from flask import Flask, request, jsonify, send_file, render_template, after_this_request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Chemin absolu vers cookies.txt
COOKIES_PATH = os.path.join(os.path.dirname(__file__), 'cookies.txt')

@app.before_request
def check_cookies_file():
    if not os.path.exists(COOKIES_PATH):
        app.logger.error(f"❌ cookies.txt introuvable à : {COOKIES_PATH}")
    else:
        app.logger.info(f"✅ cookies.txt trouvé à : {COOKIES_PATH}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/info', methods=['POST'])
def video_info():
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    try:
        import yt_dlp
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'cookies': COOKIES_PATH
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = [{
                'format_id': f.get('format_id'),
                'ext': f.get('ext'),
                'resolution': f.get('resolution') or f.get('height', ''),
                'format_note': f.get('format_note', ''),
                'filesize': f.get('filesize') or 0
            } for f in info.get('formats', []) if f.get('url') and (f.get('vcodec') != 'none' or f.get('acodec') != 'none')]

            return jsonify({
                'title': info.get('title', 'Unknown Title'),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0),
                'formats': formats
            })
    except Exception as e:
        app.logger.error("❌ Erreur d'extraction vidéo : %s", e)
        return jsonify({'error': str(e)}), 500

@app.route('/download', methods=['POST'])
def download_video():
    data = request.get_json()
    url = data.get('url')
    format_id = data.get('format_id')

    if not url or not format_id:
        return jsonify({'error': 'Missing URL or format_id'}), 400

    filename = f"video_{uuid.uuid4().hex}.mp4"
    output_path = os.path.join('/tmp', filename)

    cmd = [
        'yt-dlp',
        '--cookies', COOKIES_PATH,
        '-f', format_id,
        '-o', output_path,
        url
    ]

    try:
        app.logger.info("⏳ Téléchargement en cours avec yt-dlp...")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            app.logger.error("❌ yt-dlp error : %s", stderr.decode('utf-8'))
            return jsonify({'error': stderr.decode('utf-8')}), 500
    except Exception as e:
        app.logger.error("❌ Erreur subprocess : %s", e)
        return jsonify({'error': str(e)}), 500

    if not os.path.exists(output_path):
        return jsonify({'error': 'File not found after download'}), 500

    @after_this_request
    def cleanup(response):
        try:
            if os.path.exists(output_path):
                os.remove(output_path)
                app.logger.info("🧹 Fichier temporaire supprimé : %s", output_path)
        except Exception as e:
            app.logger.error("❌ Erreur de suppression du fichier : %s", e)
        return response

    try:
        return send_file(output_path, as_attachment=True, download_name="video.mp4")
    except Exception as e:
        app.logger.error("❌ Erreur d'envoi du fichier : %s", e)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

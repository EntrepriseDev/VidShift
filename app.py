import os
from flask import Flask, request, send_file, jsonify, render_template
import yt_dlp
import uuid
import logging

# Configuration de logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# En-têtes HTTP personnalisés pour simuler un navigateur
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/90.0.4430.93 Safari/537.36'
}

# Optionnel : utilisation d'un proxy si la variable d'environnement est définie
PROXY = os.environ.get('PROXY')  # Exemple : "http://votre-proxy:port"

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
        'http_headers': DEFAULT_HEADERS
    }
    if PROXY:
        ydl_opts['proxy'] = PROXY

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            if 'formats' not in info:
                return jsonify({'error': 'No formats available for this video.'}), 404

            formats = [{
                'format_id': f['format_id'],
                'ext': f['ext'],
                'resolution': f.get('resolution') or f.get('height', ''),
                'format_note': f.get('format_note', ''),
                'filesize': f.get('filesize') or 0
            } for f in info.get('formats', []) if f.get('vcodec') != 'none' or f.get('acodec') != 'none']

            return jsonify({
                'title': info['title'],
                'thumbnail': info['thumbnail'],
                'duration': info['duration'],
                'formats': formats
            })
    except yt_dlp.utils.DownloadError as e:
        logging.error(f"Download error: {str(e)}")
        return jsonify({'error': f"Download error: {str(e)}"}), 500
    except yt_dlp.utils.ExtractorError as e:
        logging.error(f"Extractor error: {str(e)}")
        return jsonify({'error': f"Extractor error: {str(e)}"}), 500
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

@app.route('/download', methods=['POST'])
def download_video():
    data = request.json
    url = data.get('url')
    format_id = data.get('format_id')

    if not url or not format_id:
        return jsonify({'error': 'Missing URL or format_id'}), 400

    # Utilisation d'un répertoire temporaire
    filename = f"video_{uuid.uuid4().hex}.mp4"
    output_path = os.path.join("/tmp", filename)  # Utilisation du répertoire temporaire /tmp

    ydl_opts = {
        'format': format_id,
        'outtmpl': output_path,
        'http_headers': DEFAULT_HEADERS
    }
    if PROXY:
        ydl_opts['proxy'] = PROXY

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return send_file(output_path, as_attachment=True)  # Envoi du fichier directement à l'utilisateur
    except yt_dlp.utils.DownloadError as e:
        logging.error(f"Download error: {str(e)}")
        return jsonify({'error': f"Download error: {str(e)}"}), 500
    except yt_dlp.utils.ExtractorError as e:
        logging.error(f"Extractor error: {str(e)}")
        return jsonify({'error': f"Extractor error: {str(e)}"}), 500
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

if __name__ == '__main__':
    # Port dynamique
    port = int(os.environ.get('PORT', 5000))  # Utilisation du port dynamique si disponible
    app.run(host='0.0.0.0', port=port, debug=False)

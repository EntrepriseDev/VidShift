from flask import Flask, request, jsonify, send_file, render_template, after_this_request
import os
import logging
import yt_dlp
import tempfile

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.route('/')
def index():
    """Affiche la page d'accueil."""
    return render_template('index.html')

@app.route('/info', methods=['POST'])
def video_info():
    """Récupère les infos de la vidéo (titre, thumbnail, durée, formats)."""
    data = request.get_json()
    url = data.get('url')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'cookies': 'cookies.txt'
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = [{
                'format_id': fmt.get('format_id'),
                'ext': fmt.get('ext'),
                'resolution': fmt.get('resolution') or fmt.get('height', ''),
                'format_note': fmt.get('format_note', ''),
                'filesize': fmt.get('filesize') or 0
            } for fmt in info.get('formats', []) if fmt.get('url') and (fmt.get('vcodec') != 'none' or fmt.get('acodec') != 'none')]

            return jsonify({
                'title': info.get('title', 'Unknown Title'),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0),
                'formats': formats
            })

    except Exception as e:
        app.logger.error("Error extracting video info: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/download', methods=['POST'])
def download_video():
    """Télécharge la vidéo choisie et l'envoie au client."""
    data = request.get_json()
    url = data.get('url')
    format_id = data.get('format_id')

    if not url or not format_id:
        return jsonify({'error': 'Missing URL or format_id'}), 400

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_file:
            output_path = temp_file.name

        ydl_opts = {
            'format': format_id,
            'outtmpl': output_path,
            'cookies': 'cookies.txt'
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        @after_this_request
        def remove_file(response):
            try:
                os.remove(output_path)
            except Exception as e:
                app.logger.error("Error deleting temp file: %s", e)
            return response

        return send_file(output_path, as_attachment=True, download_name="video.mp4")

    except Exception as e:
        app.logger.error("Error downloading video: %s", e)
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

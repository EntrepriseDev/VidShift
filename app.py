from flask import Flask, request, jsonify, send_file, render_template, after_this_request
import os
import logging
import yt_dlp
import tempfile

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


def extract_video_info(url: str) -> dict:
    """
    Extrait les informations de la vidéo en utilisant yt-dlp.
    Utilise le fichier cookies.txt pour contourner les limitations de YouTube.
    """
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'cookies': 'cookies.txt'
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


@app.route('/')
def index():
    """Affiche la page d'accueil."""
    return render_template('index.html')


@app.route('/info', methods=['POST'])
def video_info():
    """
    Récupère les informations de la vidéo (titre, miniature, durée, formats).
    Les formats filtrés incluent uniquement ceux avec une URL et du contenu vidéo/audio.
    """
    data = request.get_json()
    url = data.get('url')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    try:
        info = extract_video_info(url)
        formats = [
            {
                'format_id': fmt.get('format_id'),
                'ext': fmt.get('ext'),
                'resolution': fmt.get('resolution') or fmt.get('height', ''),
                'format_note': fmt.get('format_note', ''),
                'filesize': fmt.get('filesize') or 0,
                'url': fmt.get('url')
            }
            for fmt in info.get('formats', [])
            if fmt.get('url') and (fmt.get('vcodec') != 'none' or fmt.get('acodec') != 'none')
        ]
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
    """
    Télécharge la vidéo au format sélectionné, enregistre le fichier dans un emplacement temporaire,
    l'envoie au client en téléchargement, puis supprime le fichier du serveur.
    """
    data = request.get_json()
    url = data.get('url')
    format_id = data.get('format_id')
    if not url or not format_id:
        return jsonify({'error': 'Missing URL or format_id'}), 400

    try:
        # Crée un fichier temporaire pour stocker la vidéo
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
            output_path = tmp_file.name

        ydl_opts = {
            'format': format_id,
            'outtmpl': output_path,
            'cookies': 'cookies.txt',
            'quiet': True,
            'no_warnings': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        @after_this_request
        def remove_file(response):
            try:
                if os.path.exists(output_path):
                    os.remove(output_path)
                    app.logger.info("Temporary file %s removed.", output_path)
            except Exception as ex:
                app.logger.error("Error removing file: %s", ex)
            return response

        return send_file(output_path, as_attachment=True, download_name="video.mp4")

    except Exception as e:
        app.logger.error("Error downloading video: %s", e)
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)

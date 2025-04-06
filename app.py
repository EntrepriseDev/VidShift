from flask import Flask, request, jsonify, send_file, render_template, after_this_request
import os
import logging
import tempfile
from pytube import YouTube

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.route('/')
def index():
    """Affiche la page d'accueil."""
    return render_template('index.html')

@app.route('/info', methods=['POST'])
def video_info():
    """
    Extrait les informations de la vidéo avec pytube.
    Retourne le titre, la miniature, la durée et une liste de formats disponibles.
    """
    data = request.get_json()
    url = data.get('url')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    try:
        yt = YouTube(url)
        # Récupère les flux progressifs en mp4 (audio+vidéo) par ordre décroissant de résolution
        streams = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc()
        formats = [{
            'itag': stream.itag,
            'resolution': stream.resolution,
            'mime_type': stream.mime_type,
            'filesize': stream.filesize,
            'url': stream.url  # URL directe pour le streaming (optionnel)
        } for stream in streams]

        return jsonify({
            'title': yt.title,
            'thumbnail': yt.thumbnail_url,
            'duration': yt.length,
            'formats': formats
        })

    except Exception as e:
        app.logger.error("Error extracting video info: %s", e)
        return jsonify({'error': str(e)}), 500

@app.route('/download', methods=['POST'])
def download_video():
    """
    Télécharge la vidéo au format sélectionné grâce à pytube.
    La vidéo est enregistrée dans un fichier temporaire, envoyée au client,
    puis supprimée automatiquement après l'envoi.
    """
    data = request.get_json()
    url = data.get('url')
    itag = data.get('itag')  # Utilisé pour identifier le format
    if not url or not itag:
        return jsonify({'error': 'Missing URL or itag'}), 400

    try:
        yt = YouTube(url)
        stream = yt.streams.get_by_itag(itag)
        if not stream:
            return jsonify({'error': 'Stream not found for provided itag'}), 404

        # Création d'un fichier temporaire pour stocker la vidéo
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
            output_path = tmp_file.name

        # Télécharger la vidéo dans le fichier temporaire
        stream.download(
            output_path=os.path.dirname(output_path),
            filename=os.path.basename(output_path)
        )

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
    app.run(host='0.0.0.0', port=port, debug=True)

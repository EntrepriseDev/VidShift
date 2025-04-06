from flask import Flask, request, jsonify, send_file, render_template, after_this_request
import os
import uuid
import logging
import yt_dlp
import tempfile

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/info', methods=['POST'])
def video_info():
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
            } for fmt in info.get('formats', []) 
              if fmt.get('url') and (fmt.get('vcodec') != 'none' or fmt.get('acodec') != 'none')]
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
    data = request.get_json()
    url = data.get('url')
    format_id = data.get('format_id')

    if not url or not format_id:
        return jsonify({'error': 'Missing URL or format_id'}), 400

    # Création d'un fichier temporaire sécurisé pour le téléchargement
    temp_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    output_path = temp_file.name
    temp_file.close()  # Le fichier sera géré manuellement après l'envoi

    ydl_opts = {
        'format': format_id,
        'outtmpl': output_path,
        'cookies': 'cookies.txt',
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        app.logger.error("Error downloading video: %s", e)
        return jsonify({'error': str(e)}), 500

    if not os.path.exists(output_path):
        return jsonify({'error': 'File not found after download'}), 500

    @after_this_request
    def remove_file(response):
        try:
            if os.path.exists(output_path):
                os.remove(output_path)
                app.logger.info("Temporary file %s removed.", output_path)
        except Exception as e:
            app.logger.error("Error removing file: %s", e)
        return response

    try:
        return send_file(output_path, as_attachment=True, download_name="video.mp4")
    except Exception as e:
        app.logger.error("Error sending file: %s", e)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

from flask import Flask, request, jsonify, send_file, render_template, after_this_request
import yt_dlp
import os
import uuid
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.route('/')
def index():
    # Assurez-vous d'avoir un fichier index.html dans le dossier "templates"
    return render_template('index.html')

@app.route('/info', methods=['POST'])
def video_info():
    data = request.get_json()
    url = data.get('url') if data else None
    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    ydl_opts = {'quiet': True, 'skip_download': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = [
                f for f in info.get('formats', [])
                if f.get('url') and (f.get('vcodec') != 'none' or f.get('acodec') != 'none')
            ]
            clean_formats = [{
                'format_id': f.get('format_id'),
                'ext': f.get('ext'),
                'resolution': f.get('resolution') or f.get('height', ''),
                'format_note': f.get('format_note', ''),
                'filesize': f.get('filesize') or 0
            } for f in formats]

            return jsonify({
                'title': info.get('title', 'Unknown Title'),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0),
                'formats': clean_formats
            })
    except Exception as e:
        app.logger.error("Error extracting video info: %s", e)
        return jsonify({'error': str(e)}), 500

@app.route('/download', methods=['POST'])
def download_video():
    data = request.get_json()
    url = data.get('url') if data else None
    format_id = data.get('format_id') if data else None

    if not url or not format_id:
        return jsonify({'error': 'Missing URL or format_id'}), 400

    # Création d'un nom de fichier temporaire dans /tmp
    filename = f"video_{uuid.uuid4().hex}.mp4"
    output_path = os.path.join('/tmp', filename)

    ydl_opts = {
        'format': format_id,
        'outtmpl': output_path,
        'quiet': True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        app.logger.error("Error downloading video: %s", e)
        if os.path.exists(output_path):
            os.remove(output_path)
        return jsonify({'error': str(e)}), 500

    if not os.path.exists(output_path):
        app.logger.error("File not found after download.")
        return jsonify({'error': 'Failed to download video'}), 500

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
        return send_file(output_path,
                         as_attachment=True,
                         download_name="video.mp4")
    except Exception as e:
        app.logger.error("Error sending file: %s", e)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

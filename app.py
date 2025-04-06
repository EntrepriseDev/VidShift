import os
import uuid
import logging
import subprocess
from flask import Flask, request, jsonify, send_file, render_template, after_this_request

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

    try:
        import yt_dlp
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'cookiesfrombrowser': ('chrome',),  # Utilise Chrome
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
        app.logger.error("Error extracting video info: %s", e)
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
        '--cookies-from-browser', 'chrome',  # Change to 'firefox' if needed
        '-f', format_id,
        '-o', output_path,
        url
    ]

    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            app.logger.error("yt-dlp error: %s", stderr.decode('utf-8'))
            return jsonify({'error': stderr.decode('utf-8')}), 500
    except Exception as e:
        app.logger.error("Download error: %s", e)
        return jsonify({'error': str(e)}), 500

    if not os.path.exists(output_path):
        return jsonify({'error': 'Download failed. File not found.'}), 500

    @after_this_request
    def cleanup(response):
        try:
            if os.path.exists(output_path):
                os.remove(output_path)
                app.logger.info("Temporary file removed: %s", output_path)
        except Exception as e:
            app.logger.warning("Cleanup error: %s", e)
        return response

    return send_file(output_path, as_attachment=True, download_name="video.mp4")


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

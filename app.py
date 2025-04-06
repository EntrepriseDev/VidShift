from flask import Flask, request, jsonify, render_template, redirect
import yt_dlp
import logging

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

        formats = []
        for fmt in info.get('formats', []):
            if fmt.get('url') and (fmt.get('vcodec') != 'none' or fmt.get('acodec') != 'none'):
                formats.append({
                    'format_id': fmt.get('format_id'),
                    'ext': fmt.get('ext'),
                    'resolution': fmt.get('resolution') or fmt.get('height', ''),
                    'format_note': fmt.get('format_note', ''),
                    'filesize': fmt.get('filesize') or 0,
                    'url': fmt.get('url')  # lien direct
                })

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
    format_url = data.get('format_url')

    if not url or not format_url:
        return jsonify({'error': 'Missing URL or format_url'}), 400

    # Redirige l'utilisateur directement vers l'URL du fichier
    return redirect(format_url, code=302)


if __name__ == '__main__':
    app.run(debug=True)

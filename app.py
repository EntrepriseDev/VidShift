from flask import Flask, request, send_file, jsonify, render_template, after_this_request
import yt_dlp
import os
import uuid
import subprocess
import platform

app = Flask(__name__)

# Configurer le chemin des cookies
COOKIES_PATH = "cookies.txt"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/export-cookies', methods=['GET'])
def export_cookies_page():
    return render_template('export_cookies.html')

@app.route('/export-cookies', methods=['POST'])
def export_cookies():
    """
    Crée un fichier de cookies à partir du navigateur spécifié
    """
    data = request.json
    browser = data.get('browser', 'chrome')
    
    try:
        # Utiliser yt-dlp pour exporter les cookies
        subprocess.run([
            'yt-dlp',
            '--cookies-from-browser', 
            browser, 
            '--cookies', 
            COOKIES_PATH,
            '-o', 
            'NUL',  # Sur Windows
            'https://www.youtube.com'  # URL factice pour déclencher l'export
        ], check=True)
        
        return jsonify({'success': True, 'message': f'Cookies exportés depuis {browser} avec succès!'})
    except subprocess.CalledProcessError as e:
        return jsonify({'error': f'Erreur lors de l\'export des cookies: {str(e)}'}), 500

@app.route('/info', methods=['POST'])
def video_info():
    """
    Récupère les informations de la vidéo YouTube à partir de l'URL fournie.
    """
    data = request.json
    url = data.get('url')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
    }
    
    # Ajouter les cookies s'ils existent
    if os.path.exists(COOKIES_PATH):
        ydl_opts['cookiefile'] = COOKIES_PATH
    
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
                'title': info['title'],
                'thumbnail': info['thumbnail'],
                'duration': info['duration'],
                'formats': formats
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download', methods=['POST'])
def download_video():
    """
    Télécharge la vidéo YouTube en utilisant yt-dlp et l'option cookies.
    """
    data = request.json
    url = data.get('url')
    format_id = data.get('format_id')
    if not url or not format_id:
        return jsonify({'error': 'Missing URL or format_id'}), 400
    
    # S'assurer que le dossier downloads existe
    os.makedirs('downloads', exist_ok=True)
    
    filename = f"video_{uuid.uuid4().hex}.mp4"
    output_path = os.path.join("downloads", filename)
    
    ydl_opts = {
        'format': format_id,
        'outtmpl': output_path,
    }
    
    # Ajouter les cookies s'ils existent
    if os.path.exists(COOKIES_PATH):
        ydl_opts['cookiefile'] = COOKIES_PATH
    
    try:
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
            
        return send_file(output_path, as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Créer un dossier de téléchargement temporaire
    os.makedirs('downloads', exist_ok=True)
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))

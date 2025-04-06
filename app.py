from flask import Flask, request, send_file, jsonify, render_template, after_this_request
import yt_dlp
import os
import uuid
import tempfile

app = Flask(__name__)

# Cookies déjà exportés à intégrer directement dans le code
# Assurez-vous que ce fichier existe avant de déployer sur Render
COOKIES_PATH = os.environ.get("COOKIES_PATH", "cookies.txt")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/status', methods=['GET'])
def cookie_status():
    """Vérifie si les cookies sont disponibles"""
    if os.path.exists(COOKIES_PATH):
        with open(COOKIES_PATH, 'r') as f:
            cookie_content = f.read()
            cookie_lines = len(cookie_content.splitlines())
        return jsonify({
            'status': 'ok',
            'message': f'Cookies disponibles ({cookie_lines} entrées)',
            'cookies_found': True
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'Aucun fichier de cookies trouvé',
            'cookies_found': False
        })

@app.route('/upload-cookies', methods=['POST'])
def upload_cookies():
    """Permet de télécharger un fichier cookies"""
    if 'cookies' not in request.files:
        return jsonify({'error': 'Aucun fichier fourni'}), 400
    
    file = request.files['cookies']
    if file.filename == '':
        return jsonify({'error': 'Aucun fichier sélectionné'}), 400
    
    # Sauvegarder le fichier cookies
    file.save(COOKIES_PATH)
    
    return jsonify({'success': True, 'message': 'Cookies importés avec succès'})

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
    
    # Créer un dossier temporaire pour les téléchargements
    # Utiliser le système de fichiers temporaires pour Render
    temp_dir = tempfile.mkdtemp()
    filename = f"video_{uuid.uuid4().hex}.mp4"
    output_path = os.path.join(temp_dir, filename)
    
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

@app.route('/cookies-help')
def cookies_help():
    return render_template('cookies_help.html')

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))

from flask import Flask, request, send_file, jsonify, render_template
import yt_dlp
import os
import uuid
import time
import random
import logging
from datetime import datetime
from typing import Dict, List, Optional
import json
import base64

app = Flask(__name__)

# Configuration du logging avec rotation
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.handlers.RotatingFileHandler(
    'app.log', 
    maxBytes=1000000, 
    backupCount=1
)
logger.addHandler(handler)

class CustomLogger:
    def debug(self, msg):
        logger.debug(f"DEBUG: {msg}")
    
    def warning(self, msg):
        logger.warning(f"WARNING: {msg}")
    
    def error(self, msg):
        logger.error(f"ERROR: {msg}")

def get_random_user_agent() -> str:
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 11_4) AppleWebKit/537.36 Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0'
    ]
    return random.choice(user_agents)

def get_proxy() -> str:
    proxies = [
        'http://proxy1:8080',
        'http://proxy2:8080',
        'http://proxy3:8080',
        'http://proxy4:8080',
        'http://proxy5:8080'
    ]
    if random.randint(0, 100) < 10:  # Rotation des proxies
        return random.choice(proxies)
    return proxies[0]

def get_download_folder() -> str:
    folder = os.path.join('downloads', datetime.now().strftime('%Y-%m-%d'))
    os.makedirs(folder, exist_ok=True)
    return folder

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/info', methods=['POST'])
def video_info():
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'No URL provided'}), 400

        url = data['url']
        logger.info(f"Extraction des infos pour : {url}")

        cookies = load_cookies_from_env()

        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'no_call_home': True,
            'geo_bypass': True,
            'prefer_free_formats': True,
            'user_agent': get_random_user_agent(),
            'proxy': get_proxy(),
            'logger': CustomLogger(),
        }

        if cookies:
            ydl_opts['cookiefile'] = ':memory:'
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            formats = [{
                'format_id': f.get('format_id', ''),
                'ext': f.get('ext', ''),
                'resolution': f.get('resolution') or f.get('height', ''),
                'format_note': f.get('format_note', ''),
                'filesize': f.get('filesize') or 0
            } for f in info.get('formats', []) if f.get('vcodec') != 'none' or f.get('acodec') != 'none']
            
            time.sleep(random.randint(1, 3))
            
            logger.info("Extraction réussie")
            return jsonify({
                'success': True,
                'title': info.get('title', ''),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0),
                'formats': formats
            })
    except Exception as e:
        logger.error(f"Erreur lors de l'extraction des infos: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/download', methods=['POST'])
def download_video():
    output_path = None
    try:
        data = request.get_json()
        if not data or 'url' not in data or 'format_id' not in data:
            return jsonify({'error': 'Missing URL or format_id'}), 400

        url = data['url']
        format_id = data['format_id']
        logger.info(f"Téléchargement de la vidéo : {url} en format {format_id}")

        filename = f"video_{uuid.uuid4().hex}.mp4"
        output_path = os.path.join(get_download_folder(), filename)

        ydl_opts = {
            'format': format_id,
            'outtmpl': output_path,
            'no_call_home': True,
            'geo_bypass': True,
            'prefer_free_formats': True,
            'user_agent': get_random_user_agent(),
            'proxy': get_proxy(),
            'logger': CustomLogger(),
            'restrictfilenames': True,
            'merge_output_format': 'mp4',
            'write_description': True,
            'write_info_json': True,
            'write_thumbnail': True
        }

        cookies = load_cookies_from_env()
        if cookies:
            ydl_opts['cookiefile'] = ':memory:'
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            time.sleep(random.randint(2, 5))
            ydl.download([url])
            logger.info(f"Téléchargement terminé : {output_path}")
            
            return send_file(output_path, as_attachment=True)
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if output_path and os.path.exists(output_path):
            try:
                os.remove(output_path)
                logger.info(f"Fichier supprimé : {output_path}")
            except Exception as remove_error:
                logger.error(f"Erreur lors de la suppression du fichier {output_path}: {remove_error}")

def load_cookies_from_env() -> Dict:
    """Charge les cookies depuis la variable d'environnement"""
    cookies_env = os.getenv('YOUTUBE_COOKIES')
    if not cookies_env:
        return {}
    
    try:
        # Parse le JSON
        return json.loads(cookies_env)
    except json.JSONDecodeError as e:
        logger.error(f"Erreur lors du chargement des cookies: {str(e)}")
        return {}

def save_cookies_to_env(cookies: Dict):
    """Sauvegarde les cookies dans la variable d'environnement"""
    try:
        # Convertit le dictionnaire en JSON
        json_str = json.dumps(cookies)
        # Sauvegarde dans l'environnement
        os.environ['YOUTUBE_COOKIES'] = json_str
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde des cookies: {str(e)}")

if __name__ == '__main__':
    os.makedirs('downloads', exist_ok=True)
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))

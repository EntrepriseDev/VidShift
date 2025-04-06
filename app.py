from flask import Flask, request, send_file, jsonify, render_template
import yt_dlp
import os
import uuid
import time
import random
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Dict
import json

app = Flask(__name__)

# Configuration du logging avec rotation
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = RotatingFileHandler('app.log', maxBytes=1000000, backupCount=1)
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

# Rotation de proxies plus intelligente
proxy_index = 0
def get_rotating_proxy() -> str:
    global proxy_index
    proxies = [
        'http://proxy1:8080',
        'http://proxy2:8080',
        'http://proxy3:8080',
        'http://proxy4:8080',
        'http://proxy5:8080'
    ]
    proxy_index = (proxy_index + 1) % len(proxies)
    logger.info(f"Utilisation du proxy : {proxies[proxy_index]}")
    return proxies[proxy_index]

def get_headers() -> Dict[str, str]:
    return {
        "User-Agent": get_random_user_agent(),
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.youtube.com/",
        "Connection": "keep-alive",
        "DNT": "1"
    }

def human_delay(min_seconds=2, max_seconds=5):
    delay = random.uniform(min_seconds, max_seconds)
    logger.info(f"Pause simulée de {delay:.2f} secondes")
    time.sleep(delay)

def check_for_html_errors(response_text: str):
    if response_text.strip().startswith('<!DOCTYPE'):
        snippet = response_text[:500]
        logger.warning(f"Réponse HTML suspecte détectée (Captcha ou erreur) :\n{snippet}")

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
            'user_agent': get_headers()["User-Agent"],
            'proxy': get_rotating_proxy(),
            'http_headers': get_headers(),
            'logger': CustomLogger(),
        }

        if cookies:
            ydl_opts['cookiefile'] = ':memory:'
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if isinstance(info, str):
                check_for_html_errors(info)
            
            human_delay(2, 5)
            
            formats = [{
                'format_id': f.get('format_id', ''),
                'ext': f.get('ext', ''),
                'resolution': f.get('resolution') or f.get('height', ''),
                'format_note': f.get('format_note', ''),
                'filesize': f.get('filesize') or 0
            } for f in info.get('formats', []) if f.get('vcodec') != 'none' or f.get('acodec') != 'none']
            
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
            'user_agent': get_headers()["User-Agent"],
            'proxy': get_rotating_proxy(),
            'http_headers': get_headers(),
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
            human_delay(5, 10)
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
        return json.loads(cookies_env)
    except json.JSONDecodeError as e:
        logger.error(f"Erreur lors du chargement des cookies: {str(e)}")
        return {}

def save_cookies_to_env(cookies: Dict):
    """Sauvegarde les cookies dans la variable d'environnement"""
    try:
        json_str = json.dumps(cookies)
        os.environ['YOUTUBE_COOKIES'] = json_str
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde des cookies: {str(e)}")

if __name__ == '__main__':
    os.makedirs('downloads', exist_ok=True)
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))

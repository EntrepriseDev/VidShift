from flask import Flask, request, send_file, jsonify, render_template
import yt_dlp
import os
import uuid
import time
import random
import logging

app = Flask(__name__)

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Logger personnalisé pour yt-dlp
class CustomLogger:
    def debug(self, msg):
        logger.debug(msg)
    
    def warning(self, msg):
        logger.warning(msg)
    
    def error(self, msg):
        logger.error(msg)

# Liste de proxies de qualité
PROXIES = [
    'http://proxy1:8080',
    'http://proxy2:8080',
    'http://proxy3:8080',
    'http://proxy4:8080',
    'http://proxy5:8080'
]

# Fonction pour obtenir un user-agent aléatoire (retourne une chaîne)
def get_random_user_agent():
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 11_4) AppleWebKit/537.36 Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0'
    ]
    return random.choice(user_agents)

# Fonction pour obtenir un proxy aléatoire à partir d'un pool
def get_proxy():
    return random.choice(PROXIES)

# Fonction pour obtenir des headers HTTP supplémentaires
def get_extra_headers():
    return {
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.youtube.com/'
    }

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

        # Options pour yt-dlp avec headers supplémentaires et gestion potentielle des cookies
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'no_call_home': True,
            'geo_bypass': True,
            'prefer_free_formats': True,
            'user_agent': get_random_user_agent(),
            'proxy': get_proxy(),
            'http_headers': get_extra_headers(),
            # 'cookiefile': 'cookies.txt',  # Décommenter et définir le fichier de cookies si nécessaire
            'logger': CustomLogger()
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Vérification si la réponse semble être du HTML (ce qui pourrait indiquer une détection bot)
            if isinstance(info, str) and info.strip().startswith('<!DOCTYPE'):
                snippet = info[:200]  # Log des 200 premiers caractères du HTML
                logger.error(f"Réponse HTML inattendue reçue : {snippet}")
                return jsonify({'error': 'Réponse HTML inattendue, possible détection bot.'}), 500

            # Traitement des formats vidéo
            formats = [{
                'format_id': f.get('format_id', ''),
                'ext': f.get('ext', ''),
                'resolution': f.get('resolution') or f.get('height', ''),
                'format_note': f.get('format_note', ''),
                'filesize': f.get('filesize') or 0
            } for f in info.get('formats', []) if f.get('vcodec') != 'none' or f.get('acodec') != 'none']
            
            # Délai aléatoire augmenté pour imiter un comportement humain (entre 3 et 6 secondes)
            time.sleep(random.randint(3, 6))
            
            logger.info("Extraction réussie")
            return jsonify({
                'success': True,
                'title': info.get('title', ''),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0),
                'formats': formats
            })
    except Exception as e:
        error_message = str(e)
        # Si l'erreur semble contenir du HTML, logguez un extrait
        if error_message.lstrip().startswith('<!DOCTYPE'):
            snippet = error_message[:200]
            logger.error(f"Erreur HTML reçue : {snippet}")
        else:
            logger.error(f"Erreur lors de l'extraction des infos: {error_message}")
        return jsonify({'error': error_message}), 500

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

        # Création d'un nom de fichier unique
        filename = f"video_{uuid.uuid4().hex}.mp4"
        output_path = os.path.join("downloads", filename)

        ydl_opts = {
            'format': format_id,
            'outtmpl': output_path,
            'no_call_home': True,
            'geo_bypass': True,
            'prefer_free_formats': True,
            'user_agent': get_random_user_agent(),
            'proxy': get_proxy(),
            'http_headers': get_extra_headers(),
            # 'cookiefile': 'cookies.txt',  # Décommenter et définir le fichier de cookies si nécessaire
            'logger': CustomLogger()
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Délai aléatoire augmenté pour imiter un comportement humain (entre 5 et 10 secondes)
            time.sleep(random.randint(5, 10))
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

if __name__ == '__main__':
    os.makedirs('downloads', exist_ok=True)
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))

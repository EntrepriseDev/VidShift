from flask import Flask, request, send_file, jsonify, render_template, after_this_request
import yt_dlp
import os
import uuid
import tempfile
import re
import logging
import random
import time
from urllib.parse import urlparse, parse_qs

# Configuration du logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Liste des User-Agents pour rotation
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1'
]

def get_random_user_agent():
    """Renvoie un User-Agent aléatoire"""
    return random.choice(USER_AGENTS)

def transform_youtube_url(url):
    """
    Transforme une URL YouTube de différentes façons pour éviter les restrictions.
    Essaie plusieurs variantes: youtube-nocookie.com, shortened param, enlever certains params
    """
    # Si ce n'est pas une URL YouTube, renvoyer l'URL inchangée
    if not ('youtube.com' in url or 'youtu.be' in url):
        return [url]
    
    transformed_urls = []
    
    # 1. URL originale
    transformed_urls.append(url)
    
    # 2. URL youtube-nocookie.com
    nocookie_url = re.sub(r'(youtube\.com|youtu.be)', 'youtube-nocookie.com', url)
    transformed_urls.append(nocookie_url)
    
    # 3. ID de la vidéo seulement (pour youtu.be)
    if 'youtu.be' in url:
        video_id = url.split('/')[-1].split('?')[0]
        transformed_urls.append(f"https://www.youtube.com/watch?v={video_id}")
    
    # 4. Si c'est une URL youtube.com, essayons de nettoyer les paramètres
    if 'youtube.com' in url:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        
        # Garder uniquement le paramètre v (ID de la vidéo)
        if 'v' in query_params:
            video_id = query_params['v'][0]
            transformed_urls.append(f"https://www.youtube.com/watch?v={video_id}")
    
    logger.debug(f"URLs transformées: {transformed_urls}")
    return transformed_urls

@app.route('/')
def index():
    """Page d'accueil de l'application"""
    return render_template('index.html')

@app.route('/info', methods=['POST'])
def video_info():
    """
    Récupère les informations de la vidéo YouTube à partir de l'URL fournie.
    Utilise plusieurs techniques pour contourner les détections.
    """
    data = request.json
    url = data.get('url')

    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    
    logger.debug(f"Demande d'info pour l'URL: {url}")
    
    # Transformer l'URL pour contourner les restrictions
    urls_to_try = transform_youtube_url(url)
    
    # Créer les options yt-dlp avec plusieurs techniques anti-détection
    ydl_opts = {
        'quiet': False,  # Activer les logs pour le débogage
        'verbose': True,
        'skip_download': True,
        'no_warnings': False,
        # Options anti-bot
        'socket_timeout': 15,
        'retries': 3,
        'http_headers': {
            'User-Agent': get_random_user_agent(),
            'Accept-Language': 'en-US,en;q=0.9,fr;q=0.8',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Origin': 'https://www.youtube.com',
            'Referer': 'https://www.youtube.com/',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1'
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web', 'mobile', 'tv_embedded'],
                'player_skip': ['configs', 'js'],
                'compat_opt': ['no-youtube-unavailable-videos']
            }
        }
    }
    
    # Essayer chaque URL transformée jusqu'à ce qu'une fonctionne
    last_error = None
    for try_url in urls_to_try:
        try:
            logger.debug(f"Tentative avec l'URL: {try_url}")
            
            # Ajouter un délai aléatoire pour éviter la détection de bot
            time.sleep(random.uniform(0.5, 1.5))
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(try_url, download=False)
                
                # Filtrer les formats disponibles
                formats = [{
                    'format_id': f['format_id'],
                    'ext': f['ext'],
                    'resolution': f.get('resolution') or f"{f.get('height', '')}p",
                    'format_note': f.get('format_note', ''),
                    'filesize': f.get('filesize') or 0,
                    'vcodec': f.get('vcodec', 'none'),
                    'acodec': f.get('acodec', 'none')
                } for f in info.get('formats', []) if f.get('vcodec') != 'none' or f.get('acodec') != 'none']
                
                # Trier les formats par résolution
                formats.sort(key=lambda x: int(re.search(r'(\d+)p', x['resolution']).group(1)) if re.search(r'(\d+)p', x['resolution']) else 0, reverse=True)
                
                return jsonify({
                    'title': info['title'],
                    'thumbnail': info.get('thumbnail', ''),
                    'duration': info.get('duration', 0),
                    'formats': formats,
                    'description': info.get('description', '')
                })
                
        except Exception as e:
            logger.error(f"Erreur avec l'URL {try_url}: {str(e)}")
            last_error = str(e)
            continue
    
    # Si aucune URL n'a fonctionné
    error_message = last_error or "Impossible de récupérer les informations de la vidéo"
    logger.error(f"Échec final: {error_message}")
    
    # Si c'est une erreur de bot, fournir des solutions
    if "robot" in error_message.lower() or "captcha" in error_message.lower() or "bot" in error_message.lower():
        return jsonify({
            'error': f"YouTube a détecté notre service comme un bot. Erreur: {error_message}",
            'solutions': [
                "L'hébergement sur Render peut être détecté par YouTube comme un bot",
                "Essayez une autre vidéo ou réessayez plus tard",
                "Envisagez d'héberger l'application sur un VPS ou un serveur privé"
            ]
        }), 500
    
    return jsonify({'error': error_message}), 500

@app.route('/download', methods=['POST'])
def download_video():
    """
    Télécharge la vidéo YouTube avec le format choisi.
    Utilise un dossier temporaire compatible avec Render.
    """
    data = request.json
    url = data.get('url')
    format_id = data.get('format_id')
    
    if not url or not format_id:
        return jsonify({'error': 'Missing URL or format_id'}), 400
    
    logger.debug(f"Demande de téléchargement: URL={url}, format={format_id}")
    
    # Créer un dossier temporaire pour le téléchargement
    temp_dir = tempfile.mkdtemp()
    filename = f"video_{uuid.uuid4().hex}.mp4"
    output_path = os.path.join(temp_dir, filename)
    
    logger.debug(f"Chemin de sortie temporaire: {output_path}")
    
    # Transformer l'URL pour contourner les restrictions
    urls_to_try = transform_youtube_url(url)
    
    # Créer les options yt-dlp avec plusieurs techniques anti-détection
    ydl_opts = {
        'format': format_id,
        'merge_output_format': 'mp4',
        'outtmpl': output_path,
        'quiet': False,
        'verbose': True,
        'no_warnings': False,
        # Options anti-bot
        'socket_timeout': 30,
        'retries': 5,
        'http_headers': {
            'User-Agent': get_random_user_agent(),
            'Accept-Language': 'en-US,en;q=0.9,fr;q=0.8',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Origin': 'https://www.youtube.com',
            'Referer': 'https://www.youtube.com/',
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web', 'mobile', 'tv_embedded'],
                'player_skip': ['configs', 'js'],
                'compat_opt': ['no-youtube-unavailable-videos']
            }
        }
    }
    
    # Essayer chaque URL transformée jusqu'à ce qu'une fonctionne
    last_error = None
    for try_url in urls_to_try:
        try:
            logger.debug(f"Tentative de téléchargement avec l'URL: {try_url}")
            
            # Ajouter un délai aléatoire pour éviter la détection de bot
            time.sleep(random.uniform(1.0, 2.0))
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([try_url])
                
                # Vérifier si le fichier existe
                if not os.path.exists(output_path):
                    logger.error(f"Le fichier n'existe pas après le téléchargement: {output_path}")
                    continue
                
                @after_this_request
                def remove_file(response):
                    """Supprimer le fichier temporaire après l'envoi"""
                    try:
                        os.remove(output_path)
                        os.rmdir(temp_dir)
                        logger.debug("Fichiers temporaires nettoyés avec succès")
                    except Exception as e:
                        logger.error(f"Erreur lors du nettoyage des fichiers: {e}")
                    return response
                
                logger.debug(f"Téléchargement réussi, envoi du fichier: {output_path}")
                return send_file(output_path, as_attachment=True, download_name=filename)
                
        except Exception as e:
            logger.error(f"Erreur avec l'URL {try_url}: {str(e)}")
            last_error = str(e)
            continue
    
    # Si aucune URL n'a fonctionné
    error_message = last_error or "Impossible de télécharger la vidéo"
    logger.error(f"Échec final du téléchargement: {error_message}")
    
    # Nettoyer les fichiers temporaires en cas d'erreur
    try:
        if os.path.exists(output_path):
            os.remove(output_path)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage après échec: {e}")
    
    # Si c'est une erreur de bot, fournir des solutions
    if "robot" in error_message.lower() or "captcha" in error_message.lower() or "bot" in error_message.lower():
        return jsonify({
            'error': f"YouTube a détecté notre service comme un bot. Erreur: {error_message}",
            'solutions': [
                "L'hébergement sur Render peut être détecté par YouTube comme un bot",
                "Essayez une autre vidéo ou réessayez plus tard",
                "Essayez avec un format différent",
                "Envisagez d'héberger l'application sur un VPS ou un serveur privé"
            ]
        }), 500
    
    return jsonify({'error': error_message}), 500

@app.route('/health')
def health_check():
    """
    Point de terminaison pour la surveillance de la santé de l'application
    """
    return jsonify({'status': 'ok', 'version': '1.0.0'})

if __name__ == '__main__':
    # Définir le port à partir de la variable d'environnement (pour Render)
    port = int(os.environ.get("PORT", 5000))
    
    # Exécuter l'application
    app.run(debug=False, host='0.0.0.0', port=port)

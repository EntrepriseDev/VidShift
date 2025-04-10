from flask import Flask, request, send_file, jsonify, render_template, Response
import yt_dlp
import os
import uuid
import tempfile
import logging
from functools import wraps
import time
import random
import re
from pathlib import Path
import googleapiclient.discovery
import googleapiclient.errors
import json
import traceback

# Configuration
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB limite
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
TEMP_DIR = tempfile.gettempdir()

# Clés API YouTube - Utilisez plusieurs clés pour rotation et éviter les limites de quota
# Remplacez ces clés par vos véritables clés API YouTube
API_KEYS = [
    "AIzaSyAqxSfx0zZNlEQeIW8pLHfeIsCXqe-djgM",
    "YOUR_API_KEY_2",
    "YOUR_API_KEY_3"
]

# Index de la clé API actuelle
current_api_key_index = 0

# Rate limiting optimisé avec expiration automatique
rate_limit_cache = {}

def rate_limit(limit=5, per=60):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            ip = request.remote_addr
            now = time.time()
            
            # Nettoyer le cache d'anciennes données
            if random.random() < 0.01:  # 1% de chance à chaque requête
                expired = now - per * 2
                for k in list(rate_limit_cache.keys()):
                    rate_limit_cache[k] = [t for t in rate_limit_cache.get(k, []) if t > expired]
                    if not rate_limit_cache[k]:
                        rate_limit_cache.pop(k, None)
            
            # Nettoyer les anciennes requêtes pour cet IP
            if ip in rate_limit_cache:
                rate_limit_cache[ip] = [t for t in rate_limit_cache[ip] if now - t < per]
            
            # Vérifier la limite
            if ip in rate_limit_cache and len(rate_limit_cache[ip]) >= limit:
                return jsonify({"error": "Trop de requêtes. Veuillez patienter quelques instants."}), 429
            
            # Ajouter cette requête
            if ip not in rate_limit_cache:
                rate_limit_cache[ip] = []
            rate_limit_cache[ip].append(now)
                
            return f(*args, **kwargs)
        return wrapped
    return decorator

# Extraire l'ID vidéo YouTube d'une URL
def extract_video_id(url):
    # Pattern consolidé pour les URLs YouTube
    pattern = r'(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/|youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})'
    
    match = re.search(pattern, url)
    return match.group(1) if match else None

# Page d'accueil
@app.route('/')
def index():
    return render_template('index.html')

# Obtenir une clé API avec système de rotation en cas d'échec
def get_api_key():
    global current_api_key_index
    # Utiliser la clé courante
    return API_KEYS[current_api_key_index]

# Passer à la clé API suivante en cas d'erreur de quota
def rotate_api_key():
    global current_api_key_index
    # Passer à la clé suivante, de façon circulaire
    current_api_key_index = (current_api_key_index + 1) % len(API_KEYS)
    logger.info(f"Rotation de clé API: passage à l'index {current_api_key_index}")
    return API_KEYS[current_api_key_index]

# Créer une instance de l'API YouTube
def create_youtube_api(attempt=0):
    if attempt >= len(API_KEYS):
        raise Exception("Toutes les clés API YouTube sont épuisées")
    
    try:
        api_key = get_api_key()
        logger.info(f"Utilisation de la clé API: {api_key[:5]}...")
        
        return googleapiclient.discovery.build(
            "youtube", "v3", 
            developerKey=api_key,
            cache_discovery=False
        )
    except googleapiclient.errors.HttpError as e:
        error_message = str(e)
        if "quota" in error_message.lower():
            logger.warning(f"Quota dépassé pour la clé API. Rotation.")
            rotate_api_key()
            return create_youtube_api(attempt + 1)
        else:
            raise

# Obtenir les informations de la vidéo via l'API YouTube v3
@app.route('/info', methods=['POST'])
@rate_limit(limit=10, per=60)
def video_info():
    try:
        data = request.json
        url = data.get('url')
        
        if not url:
            return jsonify({'error': 'Aucune URL fournie'}), 400
        
        logger.info(f"Tentative d'extraction d'info pour URL: {url}")
        
        # Vérifier si c'est bien une URL YouTube
        video_id = extract_video_id(url)
        if not video_id:
            return jsonify({'error': 'URL YouTube non valide'}), 400
            
        logger.info(f"Video ID extrait: {video_id}")
        
        # Initialiser l'API YouTube avec système de rotation
        try:
            youtube = create_youtube_api()
            
            # Récupérer les détails de la vidéo via l'API
            request_video = youtube.videos().list(
                part="snippet,contentDetails,statistics",
                id=video_id
            )
            response = request_video.execute()
            
            # Vérifier si la vidéo existe
            if not response['items']:
                return jsonify({'error': 'Vidéo non disponible ou privée'}), 404
            
            video_data = response['items'][0]
            
            # Récupérer les détails de durée
            duration_str = video_data['contentDetails']['duration']  # Format ISO 8601
            duration = parse_duration(duration_str)
            
        except googleapiclient.errors.HttpError as e:
            try:
                error_details = json.loads(e.content.decode('utf-8'))
                error_message = error_details['error']['message']
            except:
                error_message = str(e)
            
            logger.error(f"Erreur API YouTube: {error_message}")
            
            if "quota" in error_message.lower():
                # Rotation de clé API si quota dépassé
                rotate_api_key()
                return jsonify({'error': 'Erreur temporaire du service. Veuillez réessayer.'}), 503
            else:
                return jsonify({'error': f'Erreur API YouTube: {error_message}'}), e.resp.status
        
        # Pour les formats disponibles, nous devons toujours utiliser yt-dlp
        # car l'API YouTube ne fournit pas cette information
        try:
            yt_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'youtube_include_dash_manifest': False,
                'socket_timeout': 15,
                'retries': 3
            }
            
            with yt_dlp.YoutubeDL(yt_opts) as ydl:
                formats_info = ydl.extract_info(url, download=False)
                
                # Traitement optimisé des formats
                formats = []
                for f in formats_info.get('formats', []):
                    # Ne conserver que les formats vidéo+audio ou audio seul
                    if (f.get('vcodec') != 'none' or f.get('acodec') != 'none'):
                        formats.append({
                            'format_id': f['format_id'],
                            'ext': f['ext'],
                            'resolution': f.get('resolution') or f"{f.get('height', '')}p",
                            'format_note': f.get('format_note', ''),
                            'filesize': f.get('filesize') or f.get('filesize_approx', 0)
                        })
                
                # Tri optimisé des formats
                formats.sort(key=lambda x: (0 if x['ext'] == 'mp4' else 1, -(x['filesize'] or 0)))
        
        except Exception as yt_error:
            logger.error(f"Erreur yt-dlp: {str(yt_error)}")
            # Si yt-dlp échoue, on renvoie au moins les informations de base obtenues via l'API
            formats = [{"format_id": "best", "ext": "mp4", "resolution": "Auto", "format_note": "Meilleure qualité disponible"}]
        
        # Construire le résultat avec les données de l'API et les formats de yt-dlp
        result = {
            'title': video_data['snippet']['title'],
            'thumbnail': video_data['snippet']['thumbnails']['high']['url'],
            'duration': duration,
            'view_count': video_data['statistics']['viewCount'],
            'like_count': video_data['statistics'].get('likeCount', '0'),
            'channel': video_data['snippet']['channelTitle'],
            'publish_date': video_data['snippet']['publishedAt'],
            'formats': formats[:15]  # Limiter aux 15 meilleurs formats
        }
        
        logger.info(f"Extraction API réussie pour vidéo ID: {video_id}")
        return jsonify(result)
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erreur lors de l'extraction des infos: {error_msg}")
        logger.error(traceback.format_exc())  # Ajout du stack trace complet
        return jsonify({'error': 'Erreur lors de l\'extraction des informations. Veuillez réessayer.'}), 500

# Parser la durée en format ISO 8601 (PT1H30M15S)
def parse_duration(duration_str):
    # Enlever le préfixe PT
    time_str = duration_str[2:]
    
    hours = 0
    minutes = 0
    seconds = 0
    
    # Extraire les heures, minutes et secondes
    h_match = re.search(r'(\d+)H', time_str)
    m_match = re.search(r'(\d+)M', time_str)
    s_match = re.search(r'(\d+)S', time_str)
    
    if h_match:
        hours = int(h_match.group(1))
    if m_match:
        minutes = int(m_match.group(1))
    if s_match:
        seconds = int(s_match.group(1))
    
    # Calculer la durée totale en secondes
    return hours * 3600 + minutes * 60 + seconds

# Télécharger la vidéo - Utilise yt-dlp de manière optimisée
@app.route('/download', methods=['POST'])
@rate_limit(limit=2, per=300)
def download_video():
    try:
        data = request.json
        url = data.get('url')
        format_id = data.get('format_id')
        
        if not url or not format_id:
            return jsonify({'error': 'URL ou format manquant'}), 400
        
        logger.info(f"Tentative de téléchargement pour URL: {url}, format: {format_id}")
        
        # Vérifier si c'est bien une URL YouTube
        video_id = extract_video_id(url)
        if not video_id:
            return jsonify({'error': 'URL YouTube non valide'}), 400
        
        # Créer un nom de fichier unique dans le répertoire temporaire
        filename = f"video_{uuid.uuid4().hex}.mp4"
        output_path = os.path.join(TEMP_DIR, filename)
        
        # Vérifier d'abord via l'API si la vidéo est disponible
        video_title = None
        try:
            youtube = create_youtube_api()
            
            request_video = youtube.videos().list(
                part="snippet,status",
                id=video_id
            )
            response = request_video.execute()
            
            if not response['items']:
                return jsonify({'error': 'Vidéo non disponible ou privée'}), 404
                
            video_data = response['items'][0]
            
            # Vérifier si la vidéo a des restrictions
            if video_data['status'].get('privacyStatus') == 'private':
                return jsonify({'error': 'Cette vidéo est privée.'}), 403
                
            # Récupérer le titre pour le nom du fichier
            video_title = video_data['snippet']['title']
            logger.info(f"Titre vidéo via API: {video_title}")
            
        except googleapiclient.errors.HttpError as e:
            # En cas d'erreur API, on continue avec yt-dlp
            logger.warning(f"Impossible d'obtenir les infos via API: {str(e)}")
        
        # Options de téléchargement optimisées pour yt-dlp
        ydl_opts = {
            'format': format_id,
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
            'geo_bypass': True,
            'socket_timeout': 30,
            'retries': 5,
            'fragment_retries': 5
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info(f"Téléchargement avec yt-dlp démarré")
                info = ydl.extract_info(url, download=True)
                title = video_title or info.get('title', 'video').replace('/', '_').replace('\\', '_')
                extension = info.get('ext', 'mp4')
                logger.info(f"Téléchargement terminé: {title}.{extension}")
                
                # Vérifier que le fichier a bien été créé
                if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                    raise Exception("Le fichier téléchargé est vide ou n'existe pas")
                
                # Envoyer le fichier avec le nom de la vidéo
                response = send_file(
                    output_path, 
                    as_attachment=True, 
                    download_name=f"{title}.{extension}",
                    mimetype=f"video/{extension}" if extension != 'mp3' else "audio/mpeg"
                )
                
                # Ajouter des en-têtes pour éviter les caches
                response.headers.update({
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache',
                    'Expires': '0'
                })
                
                # Nettoyage du fichier après l'envoi
                @response.call_on_close
                def cleanup():
                    try:
                        if os.path.exists(output_path):
                            os.remove(output_path)
                            logger.info(f"Fichier nettoyé: {output_path}")
                    except Exception as e:
                        logger.error(f"Erreur lors du nettoyage de fichier: {str(e)}")
                        
                logger.info(f"Téléchargement réussi pour vidéo ID: {video_id}")
                
                return response
                
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            logger.error(f"Erreur de téléchargement yt-dlp: {error_msg}")
            
            # Messages d'erreur plus spécifiques
            if "HTTP Error 429" in error_msg:
                return jsonify({'error': 'Trop de requêtes. Veuillez attendre quelques minutes avant de réessayer.'}), 429
            elif "Video unavailable" in error_msg:
                return jsonify({'error': 'Vidéo non disponible. Elle pourrait être privée ou supprimée.'}), 404
            elif "This video is available for Premium users only" in error_msg:
                return jsonify({'error': 'Cette vidéo est réservée aux utilisateurs Premium.'}), 403
            elif "Requested format is not available" in error_msg:
                return jsonify({'error': 'Le format demandé n\'est plus disponible. Veuillez actualiser et réessayer.'}), 400
            else:
                return jsonify({'error': f'Erreur lors du téléchargement: {error_msg}'}), 500
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erreur de téléchargement: {error_msg}")
        logger.error(traceback.format_exc())  # Ajout du stack trace complet
        
        # Messages d'erreur plus conviviaux
        if "HTTP Error 429" in error_msg:
            return jsonify({'error': 'Trop de requêtes. Veuillez attendre quelques minutes avant de réessayer.'}), 429
        elif "Video unavailable" in error_msg:
            return jsonify({'error': 'Vidéo non disponible. Elle pourrait être privée ou supprimée.'}), 404
        elif "This video is available for Premium users only" in error_msg:
            return jsonify({'error': 'Cette vidéo est réservée aux utilisateurs Premium.'}), 403
        else:
            return jsonify({'error': 'Erreur lors du téléchargement. Veuillez réessayer.'}), 500

# Vérifie la santé de l'application
@app.route('/health', methods=['GET'])
def health_check():
    if request.remote_addr != '127.0.0.1' and not request.remote_addr.startswith('192.168.'):
        return jsonify({'status': 'OK'}), 200
    
    try:
        # Tester rapidement l'API YouTube
        try:
            youtube = create_youtube_api()
            
            # Simple appel API pour vérifier que l'API fonctionne
            test_request = youtube.videos().list(
                part="id",
                chart="mostPopular",
                maxResults=1
            )
            test_response = test_request.execute()
            api_status = 'accessible'
        except Exception as api_error:
            api_status = f'erreur: {str(api_error)}'
        
        # Vérifier yt-dlp
        try:
            ydl_version = yt_dlp.version.__version__
            ydl_status = f'version {ydl_version}'
        except Exception as ydl_error:
            ydl_status = f'erreur: {str(ydl_error)}'
        
        status = {
            'app': 'running',
            'youtube_api': api_status,
            'yt_dlp': ydl_status,
            'temp_directory': os.path.exists(TEMP_DIR),
            'version': '2.1.0'
        }
        return jsonify(status)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Route pour tester une clé API YouTube
@app.route('/test_api_key', methods=['POST'])
def test_api_key():
    # Limiter cette fonction aux appels locaux ou administratifs
    if request.remote_addr != '127.0.0.1' and not request.remote_addr.startswith('192.168.'):
        return jsonify({'error': 'Accès non autorisé'}), 403
    
    try:
        data = request.json
        api_key = data.get('api_key')
        
        if not api_key:
            return jsonify({'error': 'Clé API manquante'}), 400
            
        # Tester la clé API
        youtube = googleapiclient.discovery.build(
            "youtube", "v3", 
            developerKey=api_key,
            cache_discovery=False
        )
        
        # Simple appel API pour vérifier le quota
        test_request = youtube.videos().list(
            part="id",
            chart="mostPopular",
            maxResults=1
        )
        response = test_request.execute()
        
        # Obtenir les informations de quota
        quota_request = youtube.quota().get()
        quota_info = quota_request.execute()
        
        return jsonify({
            'status': 'success',
            'message': 'Clé API valide',
            'quota_info': quota_info
        })
        
    except googleapiclient.errors.HttpError as e:
        try:
            error_details = json.loads(e.content.decode('utf-8'))
            error_message = error_details['error']['message']
        except:
            error_message = str(e)
            
        return jsonify({
            'status': 'error',
            'message': error_message
        }), 400
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# Fonction pour nettoyer les fichiers temporaires
def clean_temp_files():
    """Nettoie les fichiers vidéo temporaires qui pourraient rester"""
    try:
        # Recherche tous les fichiers vidéo temporaires de plus de 1 heure
        now = time.time()
        count = 0
        
        for file in os.listdir(TEMP_DIR):
            if file.startswith("video_") and (file.endswith(".mp4") or file.endswith(".webm") or file.endswith(".mp3")):
                file_path = os.path.join(TEMP_DIR, file)
                if os.path.isfile(file_path) and (now - os.path.getmtime(file_path)) > 3600:  # Plus de 1 heure
                    try:
                        os.remove(file_path)
                        count += 1
                    except Exception as e:
                        logger.error(f"Erreur lors de la suppression du fichier {file}: {str(e)}")
        
        logger.info(f"Nettoyage terminé: {count} fichiers supprimés")
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage des fichiers temporaires: {str(e)}")

# Configuration pour le démarrage
if __name__ == '__main__':
    # Créer le répertoire de téléchargement si nécessaire
    try:
        os.makedirs(TEMP_DIR, exist_ok=True)
        logger.info(f"Répertoire temporaire initialisé: {TEMP_DIR}")
    except Exception as e:
        logger.error(f"Erreur lors de la création du répertoire temporaire: {str(e)}")
    
    # Nettoyer les fichiers temporaires au démarrage
    clean_temp_files()
    
    # Démarrer le serveur
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

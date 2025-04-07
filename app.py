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
import json
from pathlib import Path
import requests
from datetime import datetime, timedelta

# Configuration améliorée
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB limite
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
TEMP_DIR = tempfile.gettempdir()

# Liste des proxies
proxy_list = [
    "http://172.67.181.112:80",
    "http://172.67.0.16:80",
    "http://104.20.75.222:80",
    "http://172.67.68.124:80",
    "http://203.24.108.86:80",
    "http://203.23.104.223:80"
]

# User agents réalistes - Optimisés et mis à jour
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1'
]

# Empreintes numériques de navigateur avancées
BROWSER_FINGERPRINTS = [
    {
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "sec-ch-ua": '"Google Chrome";v="121", "Not;A=Brand";v="8", "Chromium";v="121"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "viewport-width": "1920",
        "device-memory": "8"
    },
    {
        "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "accept-language": "en-US,en;q=0.9",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "viewport-width": "1680",
        "device-memory": "16"
    },
    {
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "accept-language": "fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "viewport-width": "1366",
        "device-memory": "4"
    }
]

# Fonction pour obtenir un proxy aléatoire
def get_random_proxy():
    return random.choice(proxy_list)

# Fonction pour obtenir une empreinte de navigateur complète
def get_browser_fingerprint():
    return random.choice(BROWSER_FINGERPRINTS)

# Fonction pour obtenir un user-agent aléatoire
def get_random_user_agent():
    return random.choice(USER_AGENTS)



# Cache pour le rate limiting - Optimisé avec expiration automatique
rate_limit_cache = {}

# Rate limiting amélioré avec nettoyage automatique des anciens enregistrements
def rate_limit(limit=5, per=60, jitter=True):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            ip = request.remote_addr
            now = time.time()
            
            # Nettoyer le cache d'anciennes données toutes les 100 requêtes
            if random.random() < 0.01:  # 1% de chance à chaque requête
                expired = now - per * 2  # Double du temps pour s'assurer que c'est vraiment expiré
                for k in list(rate_limit_cache.keys()):
                    rate_limit_cache[k] = [t for t in rate_limit_cache.get(k, []) if t > expired]
                    if not rate_limit_cache[k]:
                        rate_limit_cache.pop(k, None)
            
            # Nettoyer les anciennes requêtes pour cet IP
            if ip in rate_limit_cache:
                rate_limit_cache[ip] = [t for t in rate_limit_cache[ip] if now - t < per]
            
            # Vérifier la limite
            if ip in rate_limit_cache and len(rate_limit_cache[ip]) >= limit:
                # Délai aléatoire pour simuler un comportement humain
                if jitter:
                    time.sleep(random.uniform(1.5, 3))
                return jsonify({"error": "Trop de requêtes. Veuillez patienter quelques instants."}), 429
            
            # Ajouter cette requête
            if ip not in rate_limit_cache:
                rate_limit_cache[ip] = []
            rate_limit_cache[ip].append(now)
            
            # Léger délai aléatoire pour simuler un comportement humain
            if jitter and random.random() < 0.3:
                time.sleep(random.uniform(0.1, 0.5))
                
            return f(*args, **kwargs)
        return wrapped
    return decorator

# Fonction pour générer des valeurs de cookies YouTube aléatoires
def generate_youtube_cookies():
    # Générer un ID d'utilisateur YouTube 
    youtube_user_id = ''.join(random.choices('0123456789', k=22))
    
    # Générer un token SAPISID (important pour certaines requêtes YouTube)
    sapisid = ''.join(random.choices('0123456789', k=16))
    
    # Générer un token SID
    sid = ''.join(random.choices('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_', k=22))
    
    # Générer un token HSID
    hsid = ''.join(random.choices('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_', k=19))
    
    # Générer un token SSID
    ssid = ''.join(random.choices('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_', k=19))
    
    # Générer un token APISID
    apisid = ''.join(random.choices('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_', k=19))
    
    # Générer un token LOGIN_INFO (très important pour YouTube)
    login_info = ''.join(random.choices('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_', k=160))
    
    # Générer un timestamp pour le cookie CONSENT
    two_years_from_now = int((datetime.now() + timedelta(days=730)).timestamp())
    
    # Pour VISITOR_INFO1_LIVE (un cookie d'identification important)
    visitor_info = ''.join(random.choices('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_', k=20))
    
    # Pour YSC (exige par YouTube pour le suivi de session)
    ysc = ''.join(random.choices('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_', k=11))
    
    # PREF (préférences utilisateur)
    pref_id = f"f1{random.randint(1000000, 9999999)}"
    
    # Cookie anti-bot __Secure-YEC
    secure_yec = ''.join(random.choices('0123456789', k=10))
    
    # Générer un jeton anti-bot VISITOR_PRIVACY_METADATA
    visitor_privacy = ''.join(random.choices('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_', k=26))
    
    # Générer un jeton anti-bot pour IDE (utilisé par DoubleClick/Google)
    ide_token = ''.join(random.choices('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_', k=24))
    
    # Valeurs possibles pour le pays
    countries = ['FR', 'US', 'GB', 'DE', 'CA', 'AU']
    country = random.choice(countries)
    
    # Les langues associées aux pays
    languages = {
        'FR': 'fr-FR',
        'US': 'en-US',
        'GB': 'en-GB',
        'DE': 'de-DE',
        'CA': 'en-CA,fr-CA',
        'AU': 'en-AU'
    }
    
    lang = languages.get(country, 'en-US')
    
    return f"""# Netscape HTTP Cookie File
# http://curl.haxx.se/rfc/cookie_spec.html
# This is a generated file! Do not edit.

.youtube.com\tTRUE\t/\tFALSE\t{two_years_from_now}\tCONSENT\tYES+cb.20231125-07-p0.{country}+FX+{random.randint(100, 999)}
.youtube.com\tTRUE\t/\tFALSE\t{two_years_from_now}\tVISITOR_INFO1_LIVE\t{visitor_info}
.youtube.com\tTRUE\t/\tFALSE\t{two_years_from_now}\tPREF\t{pref_id}&tz=Europe%2FParis&f6=40000000&f5=30000
.youtube.com\tTRUE\t/\tFALSE\t{two_years_from_now}\tYSC\t{ysc}
.youtube.com\tTRUE\t/\tFALSE\t{two_years_from_now}\tLOGIN_INFO\t{login_info}
.google.com\tTRUE\t/\tFALSE\t{two_years_from_now}\tSID\t{sid}
.google.com\tTRUE\t/\tFALSE\t{two_years_from_now}\tHSID\t{hsid}
.google.com\tTRUE\t/\tFALSE\t{two_years_from_now}\tSSID\t{ssid}
.google.com\tTRUE\t/\tFALSE\t{two_years_from_now}\tAPISID\t{apisid}
.google.com\tTRUE\t/\tFALSE\t{two_years_from_now}\tSAPISID\t{sapisid}
.youtube.com\tTRUE\t/\tTRUE\t{two_years_from_now}\t__Secure-YEC\t{secure_yec}
.youtube.com\tTRUE\t/\tFALSE\t{two_years_from_now}\tVISITOR_PRIVACY_METADATA\t{visitor_privacy}
.doubleclick.net\tTRUE\t/\tFALSE\t{two_years_from_now}\tIDE\t{ide_token}
"""

# Fonction pour régénérer et actualiser les cookies
def refresh_cookies():
    cookie_path = Path(os.path.dirname(os.path.abspath(__file__))) / 'cookies.txt'
    
    try:
        # Générer de nouveaux cookies YouTube
        with open(cookie_path, 'w') as f:
            f.write(generate_youtube_cookies())
        logger.info("Fichier de cookies régénéré avec succès")
    except Exception as e:
        logger.error(f"Erreur lors de la régénération des cookies: {str(e)}")
    
    return str(cookie_path)

# Fonction pour générer un fichier de cookies YouTube valide - Optimisée avec Path
def ensure_valid_cookie():
    cookie_path = Path(os.path.dirname(os.path.abspath(__file__))) / 'cookies.txt'
    
    # Si le fichier de cookies n'existe pas ou est vide, on crée un fichier avec des cookies réalistes
    if not cookie_path.exists() or cookie_path.stat().st_size == 0:
        try:
            with open(cookie_path, 'w') as f:
                f.write(generate_youtube_cookies())
            logger.info("Fichier de cookies créé avec succès")
        except Exception as e:
            logger.error(f"Erreur lors de la création du fichier de cookies: {str(e)}")
    
    # Régénérer occasionnellement les cookies pour éviter la détection
    elif random.random() < 0.1:  # 10% de chance de régénérer les cookies
        return refresh_cookies()
    
    return str(cookie_path)

# Extraire l'ID vidéo YouTube d'une URL - Méthode optimisée et plus robuste
def extract_video_id(url):
    # Pattern consolidé pour les URLs YouTube
    pattern = r'(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/|youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})'
    
    match = re.search(pattern, url)
    return match.group(1) if match else None

# Page d'accueil - Utilise le template existant
@app.route('/')
def index():
    return render_template('index.html')

# Obtenir les informations de la vidéo - Optimisé avec rotation de proxy
@app.route('/info', methods=['POST'])
@rate_limit(limit=10, per=60)
def video_info():
    try:
        data = request.json
        url = data.get('url')
        
        if not url:
            return jsonify({'error': 'Aucune URL fournie'}), 400
        
        # Vérifier si c'est bien une URL YouTube
        video_id = extract_video_id(url)
        if not video_id:
            return jsonify({'error': 'URL YouTube non valide'}), 400
            
        # Petite pause aléatoire pour simuler un comportement humain
        if random.random() < 0.5:
            time.sleep(random.uniform(0.2, 0.7))
        
        # Configuration avancée pour contourner les limitations de YouTube
        cookie_path = ensure_valid_cookie()
        
        # Obtenir une empreinte de navigateur complète
        browser_fingerprint = get_browser_fingerprint()
        user_agent = browser_fingerprint["userAgent"]
        
        # Sélectionner un proxy aléatoire
        proxy = get_random_proxy()
        
        # Options améliorées avec empreinte numérique complète et proxy
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'format': 'best',
            'extractor_args': {
                'youtube': {
                    'skip': ['dash', 'hls'],
                    'player_client': ['web', 'android'],
                    'innertube_client': ['web', 'android'],
                }
            },
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'geo_bypass': True,
            'geo_bypass_country': 'US',
            'cookiefile': cookie_path,
            'user_agent': user_agent,
            'http_headers': {
                'User-Agent': user_agent,
                'Accept': browser_fingerprint.get('accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'),
                'Accept-Language': browser_fingerprint.get('accept-language', 'en-us,en;q=0.5'),
                'Sec-Fetch-Mode': browser_fingerprint.get('sec-fetch-mode', 'navigate'),
                'Sec-Fetch-Dest': browser_fingerprint.get('sec-fetch-dest', 'document'),
                'Sec-Fetch-Site': browser_fingerprint.get('sec-fetch-site', 'none'),
                'Sec-Ch-Ua': browser_fingerprint.get('sec-ch-ua', ''),
                'Sec-Ch-Ua-Mobile': browser_fingerprint.get('sec-ch-ua-mobile', '?0'),
                'Sec-Ch-Ua-Platform': browser_fingerprint.get('sec-ch-ua-platform', ''),
                'Viewport-Width': browser_fingerprint.get('viewport-width', '1920'),
                'Device-Memory': browser_fingerprint.get('device-memory', '8'),
                'Origin': 'https://www.youtube.com',
                'Referer': f'https://www.youtube.com/watch?v={video_id}'
            },
            'socket_timeout': 15,
            'source_address': '0.0.0.0',
            'sleep_interval': random.randint(1, 3),
            'max_sleep_interval': 5,
            'proxy': proxy  # Utilisation du proxy
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Ajout d'un délai aléatoire pour simuler un comportement humain
            time.sleep(random.uniform(0.5, 1.5))
            
            info = ydl.extract_info(url, download=False)
            
            # Traitement optimisé des formats
            formats = []
            for f in info.get('formats', []):
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
            
            result = {
                'title': info['title'],
                'thumbnail': info.get('thumbnail', ''),
                'duration': info['duration'],
                'formats': formats[:15]  # Limiter aux 15 meilleurs formats
            }
            
            logger.info(f"Extraction réussie pour vidéo ID: {video_id}")
            
            return jsonify(result)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erreur lors de l'extraction des infos: {error_msg}")
        
        # Messages d'erreur plus conviviaux
        if "Video unavailable" in error_msg:
            return jsonify({'error': 'Vidéo non disponible. Elle pourrait être privée ou supprimée.'}), 404
        elif "This video is available for Premium users only" in error_msg:
            return jsonify({'error': 'Cette vidéo est réservée aux utilisateurs Premium.'}), 403
        elif "Sign in to confirm your age" in error_msg:
            return jsonify({'error': 'Cette vidéo nécessite une vérification d\'âge.'}), 403
        elif "Unable to extract" in error_msg or "HTTP Error" in error_msg:
            # Essayer un autre proxy en cas d'erreur
            return jsonify({'error': 'Erreur temporaire. Veuillez réessayer dans quelques instants.'}), 503
        else:
            return jsonify({'error': 'Erreur lors de l\'extraction des informations. Veuillez réessayer.'}), 500

# Télécharger la vidéo - Optimisé avec rotation de proxy et empreinte numérique avancée
@app.route('/download', methods=['POST'])
@rate_limit(limit=2, per=300, jitter=True)  # Limite stricte pour les téléchargements
def download_video():
    try:
        data = request.json
        url = data.get('url')
        format_id = data.get('format_id')
        
        if not url or not format_id:
            return jsonify({'error': 'URL ou format manquant'}), 400
        
        # Vérifier si c'est bien une URL YouTube
        video_id = extract_video_id(url)
        if not video_id:
            return jsonify({'error': 'URL YouTube non valide'}), 400
        
        # Créer un nom de fichier unique dans le répertoire temporaire
        filename = f"video_{uuid.uuid4().hex}.mp4"
        output_path = os.path.join(TEMP_DIR, filename)
        
        # Configuration avancée pour éviter la détection
        cookie_path = ensure_valid_cookie()
        
        # Obtenir une empreinte de navigateur complète
        browser_fingerprint = get_browser_fingerprint()
        user_agent = browser_fingerprint["userAgent"]
        
        # Sélectionner un proxy aléatoire
        proxy = get_random_proxy()
        
        # Ajout d'un délai aléatoire pour simuler un comportement humain
        time.sleep(random.uniform(1.0, 2.5))
        
        # Options de téléchargement optimisées avec empreinte numérique complète
        ydl_opts = {
            'format': format_id,
            'outtmpl': output_path,
            'quiet': True,
            'nocheckcertificate': True,
            'geo_bypass': True,
            'geo_bypass_country': random.choice(['US', 'CA', 'GB', 'FR', 'DE']),
            'cookiefile': cookie_path,
            'user_agent': user_agent,
            'http_headers': {
                'User-Agent': user_agent,
                'Accept': browser_fingerprint.get('accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'),
                'Accept-Language': browser_fingerprint.get('accept-language', 'en-us,en;q=0.5'),
                'Sec-Fetch-Mode': browser_fingerprint.get('sec-fetch-mode', 'navigate'),
                'Sec-Fetch-Dest': browser_fingerprint.get('sec-fetch-dest', 'document'),
                'Sec-Fetch-Site': browser_fingerprint.get('sec-fetch-site', 'none'),
                'Sec-Ch-Ua': browser_fingerprint.get('sec-ch-ua', ''),
                'Sec-Ch-Ua-Mobile': browser_fingerprint.get('sec-ch-ua-mobile', '?0'),
                'Sec-Ch-Ua-Platform': browser_fingerprint.get('sec-ch-ua-platform', ''),
                'Viewport-Width': browser_fingerprint.get('viewport-width', '1920'),
                'Device-Memory': browser_fingerprint.get('device-memory', '8'),
                'Origin': 'https://www.youtube.com',
                'Referer': f'https://www.youtube.com/watch?v={video_id}'
            },
            'socket_timeout': 30,
            'retries': 10,
            'fragment_retries': 10,
            'hls_prefer_native': random.choice([True, False]),
            'external_downloader_args': ['-loglevel', 'panic'],
            'sleep_interval': random.randint(1, 3),
            'max_sleep_interval': 5,
            'extractor_args': {
                'youtube': {
                    'player_client': ['web', 'android', 'mobile'],
                    'player_skip': random.choice([None, 'configs', 'webpage']),
                    'innertube_client': ['web', 'android', 'embedded'],
                }
            },
            'proxy': proxy  # Utilisation du proxy
        }
        
        # Tentative avec rotation de proxy en cas d'échec
        max_retries = 3
        for retry in range(max_retries):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    title = info.get('title', 'video').replace('/', '_').replace('\\', '_')
                    extension = info.get('ext', 'mp4')
                break  # Si réussi, on sort de la boucle
            except Exception as e:
                if retry < max_retries - 1:
                    logger.warning(f"Tentative {retry+1} échouée. Changement de proxy...")
                    # Changer de proxy et de cookies pour la prochaine tentative
                    ydl_opts['proxy'] = get_random_proxy()
                    ydl_opts['cookiefile'] = refresh_cookies()
                    time.sleep(random.uniform(1.5, 3.0))
                else:
                    raise e
        
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
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erreur de téléchargement: {error_msg}")
        
        # Messages d'erreur plus conviviaux
        if "HTTP Error 429" in error_msg:
            return jsonify({'error': 'Trop de requêtes. Veuillez attendre quelques minutes avant de réessayer.'}), 429
        elif "Video unavailable" in error_msg:
            return jsonify({'error': 'Vidéo non disponible. Elle pourrait être privée ou supprimée.'}), 404
        elif "This video is available for Premium users only" in error_msg:
            return jsonify({'error': 'Cette vidéo est réservée aux utilisateurs Premium.'}), 403
        elif "Unable to extract" in error_msg or "HTTP Error" in error_msg:
            # Essayer de changer de proxy et cookies en cas d'erreur
            refresh_cookies()
            return jsonify({'error': 'Erreur temporaire. Veuillez réessayer dans quelques instants.'}), 503
        else:
            return jsonify({'error': 'Erreur lors du téléchargement. Veuillez réessayer.'}), 500

# Fonction pour tester et vérifier la validité des proxies
@app.route('/test_proxies', methods=['GET'])
def test_proxies():
    if request.remote_addr != '127.0.0.1' and not request.remote_addr.startswith('192.168.'):
        return jsonify({'error': 'Accès non autorisé'}), 403
        
    results = []
    for proxy in proxy_list:
        try:
            # Tester le proxy avec une requête à YouTube
            response = requests.get(
                'https://www.youtube.com/robots.txt', 
                proxies={'http': proxy, 'https': proxy}, 
                timeout=5,
                headers={'User-Agent': get_random_user_agent()}
            )
            results.append({
                'proxy': proxy,
                'status': 'OK' if response.status_code == 200 else 'ERREUR',
                'code': response.status_code,
                'time': response.elapsed.total_seconds()
            })
        except Exception as e:
            results.append({
                'proxy': proxy,
                'status': 'ERREUR',
                'error': str(e)
            })
    
    return jsonify(results)

# Route pour la régénération des cookies - accessible uniquement en local
@app.route('/refresh_cookies', methods=['GET'])
def refresh_cookies_route():
    if request.remote_addr != '127.0.0.1' and not request.remote_addr.startswith('192.168.'):
        return jsonify({'error': 'Accès non autorisé'}), 403
        
    try:
        cookie_path = refresh_cookies()
        return jsonify({'success': True, 'message': f'Cookies régénérés avec succès: {cookie_path}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Fonction pour vérifier l'état du service YouTube
def check_youtube_status():
    """Vérifie si YouTube est accessible et fonctionne correctement"""
    working_proxies = []
    
    for proxy in proxy_list:
        try:
            browser_fingerprint = get_browser_fingerprint()
            user_agent = browser_fingerprint["userAgent"]
            
            response = requests.get(
                'https://www.youtube.com/robots.txt', 
                proxies={'http': proxy, 'https': proxy}, 
                timeout=5,
                headers={
                    'User-Agent': user_agent,
                    'Accept': browser_fingerprint.get('accept', '*/*'),
                    'Accept-Language': browser_fingerprint.get('accept-language', 'en-US,en;q=0.9')
                }
            )
            
            if response.status_code == 200:
                working_proxies.append(proxy)
                
        except Exception:
            continue
    
    return len(working_proxies) > 0

# Vérification régulière de la validité des cookies et des proxies
def scheduled_maintenance():
    """Effectue des vérifications périodiques des ressources et les actualise si nécessaire"""
    try:
        # Vérifier si YouTube est accessible
        youtube_ok = check_youtube_status()
        
        if not youtube_ok:
            logger.warning("YouTube semble inaccessible avec les proxies actuels.")
            # Logique pour essayer d'obtenir de nouveaux proxies ou notifier l'administrateur
        
        # Régénérer régulièrement les cookies pour éviter la détection
        refresh_cookies()
        
        # Nettoyer les fichiers temporaires
        clean_temp_files()
        
        logger.info("Maintenance planifiée terminée avec succès")
    except Exception as e:
        logger.error(f"Erreur lors de la maintenance planifiée: {str(e)}")

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

# Vérifie la santé de l'application
@app.route('/health', methods=['GET'])
def health_check():
    if request.remote_addr != '127.0.0.1' and not request.remote_addr.startswith('192.168.'):
        return jsonify({'status': 'OK'}), 200
    
    try:
        status = {
            'app': 'running',
            'youtube_accessible': check_youtube_status(),
            'temp_directory': os.path.exists(TEMP_DIR),
            'cookies_file': os.path.exists(Path(os.path.dirname(os.path.abspath(__file__))) / 'cookies.txt'),
            'version': '1.2.0'
        }
        return jsonify(status)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Configuration pour le démarrage
if __name__ == '__main__':
    # Créer le répertoire de téléchargement si nécessaire
    try:
        os.makedirs(TEMP_DIR, exist_ok=True)
        logger.info(f"Répertoire temporaire initialisé: {TEMP_DIR}")
    except Exception as e:
        logger.error(f"Erreur lors de la création du répertoire temporaire: {str(e)}")
    
    # S'assurer que le cookie existe
    ensure_valid_cookie()
    
    # Effectuer une première maintenance
    scheduled_maintenance()
    
    # Démarrer le serveur
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

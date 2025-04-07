from flask import Flask, request, send_file, jsonify, render_template
import yt_dlp
import os
import time
import random
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Dict, Optional, List
import json
import requests
from urllib.parse import urlparse, parse_qs
import string
import hashlib
import re
import threading
import tempfile

app = Flask(__name__)

# Configuration du logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = RotatingFileHandler('app.log', maxBytes=1_000_000, backupCount=3)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class CustomLogger:
    def debug(self, msg):
        logger.debug(msg)
    
    def warning(self, msg):
        logger.warning(msg)
    
    def error(self, msg):
        logger.error(msg)
        
    def info(self, msg):
        logger.info(msg)

# Cache pour les informations vidéo
video_cache = {}

def get_user_agent() -> str:
    """Fournit un User-Agent réaliste et moderne pour 2025"""
    agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.6558.58 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5_1) AppleWebKit/615.1.15 (KHTML, like Gecko) Version/18.4 Safari/615.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.6512.83 Safari/537.36',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 18_4_1 like Mac OS X) AppleWebKit/608.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/607.1',
        'Mozilla/5.0 (iPad; CPU OS 18_4_2 like Mac OS X) AppleWebKit/608.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/607.1',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.6455.89 Safari/537.36 Edg/127.0.2591.67',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.6588.92 Safari/537.36'
    ]
    return random.choice(agents)

def get_proxy() -> Optional[str]:
    """Système optimisé de sélection de proxy"""
    proxy_list = [
        "http://172.67.181.112:80",
        "http://172.67.0.16:80",
        "http://104.20.75.222:80",
        "http://172.67.68.124:80",
        "http://203.24.108.86:80",
        "http://203.23.104.223:80"
    ]
    
    # Ajouter des proxies personnalisés si définis
    custom_proxies = os.getenv('CUSTOM_PROXIES')
    if custom_proxies:
        try:
            additional_proxies = json.loads(custom_proxies)
            if isinstance(additional_proxies, list):
                proxy_list.extend(additional_proxies)
        except:
            pass
    
    # Mélanger la liste pour éviter les patterns
    random.shuffle(proxy_list)
    
    # Si nous avons un fichier de proxies testés et récents
    proxy_cache_file = os.path.join(tempfile.gettempdir(), "working_proxies.json")
    if os.path.exists(proxy_cache_file):
        try:
            # Vérifier si le fichier est assez récent (moins de 12 heures)
            if (time.time() - os.path.getmtime(proxy_cache_file)) < 43200:
                with open(proxy_cache_file, 'r') as f:
                    working_proxies = json.load(f)
                if working_proxies:
                    return random.choice(working_proxies)
        except:
            pass
    
    # Si aucun proxy fonctionnel trouvé, effectuer un test rapide
    working_proxies = []
    for proxy in random.sample(proxy_list, min(3, len(proxy_list))):
        try:
            response = requests.get("https://www.youtube.com", 
                                   proxies={"http": proxy, "https": proxy},
                                   headers={"User-Agent": get_user_agent()},
                                   timeout=3)
            if response.status_code == 200:
                working_proxies.append(proxy)
                logger.info(f"Proxy fonctionnel: {proxy}")
        except:
            pass
    
    # Enregistrer les proxies fonctionnels
    if working_proxies:
        try:
            with open(proxy_cache_file, 'w') as f:
                json.dump(working_proxies, f)
        except:
            pass
        return random.choice(working_proxies)
    
    logger.warning("Aucun proxy disponible")
    return None

def get_headers(url: str) -> Dict[str, str]:
    """Génère des en-têtes HTTP réalistes basés sur l'URL"""
    user_agent = get_user_agent()
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    
    # En-têtes de base réalistes pour 2025
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate", 
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Sec-Ch-Ua": '"Not A(Brand";v="99", "Google Chrome";v="128", "Chromium";v="128"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"' if "Windows" in user_agent else ('"macOS"' if "Mac" in user_agent else '"Linux"'),
        "Priority": "u=0, i"
    }
    
    # Ajout d'un referer réaliste pour YouTube
    if "youtube" in domain:
        possible_referers = [
            "https://www.google.com/search?q=youtube+videos",
            f"https://{domain}/results?search_query=trending",
            "https://www.reddit.com/r/videos/",
            None  # Parfois pas de referer (accès direct)
        ]
        referer = random.choice(possible_referers)
        if referer:
            headers["Referer"] = referer
    
    return headers

def delay(min_time=0.5, max_time=2.0):
    """Simule un délai humain naturel"""
    time.sleep(random.uniform(min_time, max_time))

def generate_filename(video_title: str, ext: str) -> str:
    """Génère un nom de fichier sécurisé basé sur le titre"""
    # Nettoyer le titre pour un nom de fichier valide
    valid_chars = f"-_.() {string.ascii_letters}{string.digits}"
    safe_title = ''.join(c for c in video_title if c in valid_chars)
    safe_title = re.sub(r'\s+', ' ', safe_title).strip()[:50]
    
    # Ajouter un identifiant unique
    unique_id = hashlib.md5(f"{video_title}{time.time()}".encode()).hexdigest()[:6]
    
    return f"{safe_title}_{unique_id}.{ext}"

def get_download_folder() -> str:
    """Crée et retourne un dossier de téléchargement organisé"""
    folder = os.path.join('downloads', datetime.now().strftime('%Y-%m-%d'))
    os.makedirs(folder, exist_ok=True)
    return folder

def create_cookie_file() -> Optional[str]:
    """Crée un fichier de cookies temporaire"""
    cookie_path = os.getenv('COOKIE_PATH', 'cookies.txt')
    
    if os.path.exists(cookie_path):
        temp_file = os.path.join(tempfile.gettempdir(), f"yt_cookies_{int(time.time())}.txt")
        try:
            with open(cookie_path, 'r', encoding='utf-8', errors='ignore') as src, open(temp_file, 'w') as dest:
                dest.write(src.read())
            logger.info(f"Fichier de cookies créé: {temp_file}")
            return temp_file
        except Exception as e:
            logger.error(f"Erreur création cookies: {e}")
    
    return None

def extract_video_id(url):
    """Extrait l'ID de la vidéo YouTube de l'URL"""
    video_id = None
    
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/v\/([a-zA-Z0-9_-]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1)
            break
    
    if not video_id:
        parsed_url = urlparse(url)
        if 'youtube.com' in parsed_url.netloc:
            params = parse_qs(parsed_url.query)
            if 'v' in params:
                video_id = params['v'][0]
    
    return video_id

def preprocess_url(url):
    """Prétraite l'URL pour éviter les détections"""
    video_id = extract_video_id(url)
    if not video_id:
        return url
    
    # Alterner entre différents formats d'URL
    urls = [
        f"https://www.youtube.com/watch?v={video_id}",
        f"https://youtu.be/{video_id}",
        f"https://www.youtube.com/embed/{video_id}"
    ]
    
    return random.choice(urls)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/info', methods=['POST'])
def video_info():
    temp_cookie_file = None
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'URL non fournie'}), 400

        url = data['url']
        logger.info(f"Demande d'info pour: {url}")
        
        # Simulation de comportement utilisateur
        delay(1, 2)
        
        # Vérification du cache
        video_id = extract_video_id(url)
        if video_id and video_id in video_cache and time.time() - video_cache[video_id]['timestamp'] < 3600:
            logger.info(f"Utilisation du cache pour {video_id}")
            return jsonify(video_cache[video_id]['data'])
        
        # Prétraitement de l'URL pour éviter la détection
        processed_url = preprocess_url(url)
        
        # Options optimisées pour 2025 selon la dernière documentation yt-dlp
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'no_call_home': True,
            'geo_bypass': True,
            'http_headers': get_headers(processed_url),
            'logger': CustomLogger(),
            'socket_timeout': 20,
            'retries': 5,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            
            # Options cruciales pour contourner les limitations (2025)
            'extractor_args': {
                'youtube': {
                    'player_client': ['web', 'android', 'ios'],  # Plusieurs clients
                    'player_skip': ['js'],  # Éviter JS extraction
                    'innertube_host': 'www.youtube.com',  # Utiliser hôte principal  
                    'innertube_key': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',  # Clé alternative
                    'innertube_client': {
                        'client_name': 'WEB',
                        'client_version': '2.20250325.01.00'  # Version 2025 pour match
                    }
                }
            },
            'dynamic_mpd': True,  # Utiliser MPD dynamique si disponible
            
            # Nouvelles options 2025
            'throttled_rate': '100K',  # Limiter débit pour paraître plus naturel
            'force_generic_extractor': False,
            'concurrent_fragment_downloads': 1,  # Éviter parallélisme suspect
        }
        
        # Utilisation d'un proxy
        proxy = get_proxy()
        if proxy:
            ydl_opts['proxy'] = proxy
        
        # Utilisation des cookies
        temp_cookie_file = create_cookie_file()
        if temp_cookie_file:
            ydl_opts['cookiefile'] = temp_cookie_file
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Courte pause naturelle
                delay(0.5, 1.5)
                
                # Extraction avec comportement humain
                info = ydl.extract_info(processed_url, download=False)
                
                # Traitement des formats disponibles
                formats = [{
                    'format_id': f.get('format_id', ''),
                    'ext': f.get('ext', ''),
                    'resolution': f.get('resolution') or (f"{f.get('height', '')}p" if f.get('height') else ''),
                    'format_note': f.get('format_note', ''),
                    'filesize': f.get('filesize', 0) or f.get('filesize_approx', 0) or 0,
                    'vcodec': f.get('vcodec', ''),
                    'acodec': f.get('acodec', '')
                } for f in info.get('formats', []) if not (f.get('vcodec') == 'none' and f.get('acodec') == 'none')]
                
                # Filtrer pour éliminer les doublons et organiser par qualité
                unique_formats = {}
                for fmt in formats:
                    # Créer une clé unique basée sur la résolution et le type
                    key = f"{fmt['resolution']}_{fmt['ext']}"
                    if key not in unique_formats or fmt['filesize'] > unique_formats[key]['filesize']:
                        unique_formats[key] = fmt
                
                # Trier par qualité (résolution)
                sorted_formats = sorted(
                    unique_formats.values(), 
                    key=lambda x: (0 if not x['resolution'] else 
                                  int(x['resolution'].replace('p', '')) if x['resolution'].replace('p', '').isdigit() else 0), 
                    reverse=True
                )
                
                # Préparer les données de réponse
                response_data = {
                    'success': True,
                    'title': info.get('title', ''),
                    'thumbnail': info.get('thumbnail', ''),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', ''),
                    'formats': sorted_formats
                }
                
                # Mise en cache
                if video_id:
                    video_cache[video_id] = {
                        'timestamp': time.time(),
                        'data': response_data
                    }
                
                logger.info(f"Extraction réussie: {info.get('title', '')}")
                return jsonify(response_data)
                
        except Exception as e:
            logger.error(f"Erreur d'extraction: {str(e)}")
            return jsonify({'error': f"Erreur lors de l'extraction: {str(e)}"}), 500
        
    except Exception as e:
        logger.error(f"Erreur générale: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        # Nettoyage du fichier temporaire
        if temp_cookie_file and os.path.exists(temp_cookie_file):
            try:
                os.remove(temp_cookie_file)
            except:
                pass

@app.route('/download', methods=['POST'])
def download_video():
    output_path = None
    temp_cookie_file = None
    try:
        data = request.get_json()
        if not data or 'url' not in data or 'format_id' not in data:
            return jsonify({'error': 'URL ou format_id manquant'}), 400

        url = data['url']
        format_id = data['format_id']
        
        # Prétraitement de l'URL
        processed_url = preprocess_url(url)
        
        # Extraction du titre pour le nom de fichier
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'skip_download': True}) as ydl:
                info = ydl.extract_info(processed_url, download=False)
                title = info.get('title', 'video')
        except:
            title = f"youtube_video_{int(time.time())}"
        
        # Génération du nom de fichier
        safe_filename = generate_filename(title, 'mp4')
        output_path = os.path.join(get_download_folder(), safe_filename)
        
        logger.info(f"Téléchargement: {title} (format {format_id})")
        
        # Simulation comportement humain
        delay(1, 3)
        
        # Configuration avancée pour le téléchargement
        ydl_opts = {
            'format': format_id,
            'outtmpl': output_path,
            'no_call_home': True,
            'geo_bypass': True,
            'http_headers': get_headers(processed_url),
            'logger': CustomLogger(),
            'merge_output_format': 'mp4',
            'fragment_retries': 10,
            'retries': 5,
            'nocheckcertificate': True,
            
            # Options cruciales pour contourner les limitations (2025)
            'extractor_args': {
                'youtube': {
                    'player_client': ['web', 'android', 'ios'],
                    'player_skip': ['js'],
                    'innertube_host': 'www.youtube.com',
                    'innertube_key': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
                    'innertube_client': {
                        'client_name': 'WEB',
                        'client_version': '2.20250325.01.00'
                    }
                }
            },
            
            # Options de postprocessing
            'postprocessors': [{
                'key': 'FFmpegMetadata',
                'add_metadata': True,
            }],
            
            # Options avancées pour éviter la détection
            'throttled_rate': '512K',  # Limiter le débit pour paraître naturel
            'concurrent_fragment_downloads': 2,  # Modéré pour éviter la détection
            'dynamic_mpd': True,
        }
        
        # Utilisation d'un proxy différent
        proxy = get_proxy()
        if proxy:
            ydl_opts['proxy'] = proxy
        
        # Utilisation des cookies
        temp_cookie_file = create_cookie_file()
        if temp_cookie_file:
            ydl_opts['cookiefile'] = temp_cookie_file
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Simulation d'interactions humaines
                delay(1, 2)
                
                # Téléchargement
                ydl.download([processed_url])
                
                logger.info(f"Téléchargement terminé: {output_path}")
                
                # Envoyer le fichier
                return send_file(
                    output_path, 
                    as_attachment=True,
                    download_name=safe_filename,
                    mimetype='video/mp4'
                )
        finally:
            # Nettoyage
            if temp_cookie_file and os.path.exists(temp_cookie_file):
                try:
                    os.remove(temp_cookie_file)
                except:
                    pass
    except Exception as e:
        logger.error(f"Erreur de téléchargement: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        # Nettoyage du fichier téléchargé
        if output_path and os.path.exists(output_path):
            try:
                if os.getenv('KEEP_FILES') != 'true':
                    os.remove(output_path)
                    logger.info(f"Fichier supprimé: {output_path}")
            except Exception as e:
                logger.error(f"Erreur de suppression: {str(e)}")

@app.route('/health')
def health_check():
    """Point de terminaison pour vérifier l'état du service"""
    return jsonify({'status': 'ok', 'time': datetime.now().isoformat()})

if __name__ == '__main__':
    os.makedirs('downloads', exist_ok=True)
    
    # Création du fichier HTML si manquant
    templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    os.makedirs(templates_dir, exist_ok=True)
    
    index_html = os.path.join(templates_dir, 'index.html')
    if not os.path.exists(index_html):
        with open(index_html, 'w') as f:
            f.write('''<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Youtube Downloader Pro</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/tailwindcss/2.2.19/tailwind.min.css" rel="stylesheet">
    <style>
        .loader {
            border-top-color: #3498db;
            -webkit-animation: spinner 1.5s linear infinite;
            animation: spinner 1.5s linear infinite;
        }
        
        @-webkit-keyframes spinner {
            0% { -webkit-transform: rotate(0deg); }
            100% { -webkit-transform: rotate(360deg); }
        }
        
        @keyframes spinner {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body class="bg-gray-100 min-h-screen">
    <div class="container mx-auto px-4 py-8">
        <div class="text-center mb-10">
            <h1 class="text-4xl font-bold text-blue-600 mb-2">Youtube Downloader Pro</h1>
            <p class="text-gray-600">Téléchargez facilement des vidéos YouTube en haute qualité</p>
        </div>
        
        <div class="max-w-3xl mx-auto bg-white rounded-lg shadow-md p-6">
            <div class="mb-6">
                <label for="url" class="block text-gray-700 font-medium mb-2">URL de la vidéo YouTube</label>
                <div class="flex">
                    <input type="text" id="url" class="flex-grow px-4 py-2 border border-gray-300 rounded-l focus:outline-none focus:ring-2 focus:ring-blue-500" 
                           placeholder="https://www.youtube.com/watch?v=...">
                    <button id="getInfo" class="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-r transition-colors">
                        Analyser
                    </button>
                </div>
            </div>
            
            <!-- Loader -->
            <div id="loader" class="hidden">
                <div class="flex justify-center items-center py-8">
                    <div class="loader ease-linear rounded-full border-4 border-t-4 border-gray-200 h-12 w-12"></div>
                </div>
                <p class="text-center text-gray-600">Récupération des informations...</p>
            </div>
            
            <!-- Error message -->
            <div id="error" class="hidden bg-red-100 border-l-4 border-red-500 text-red-700 p-4 mb-6" role="alert">
                <p id="errorMessage"></p>
            </div>
            
            <!-- Video info -->
            <div id="videoInfo" class="hidden">
                <div class="flex flex-col md:flex-row mb-6">
                    <div class="md:w-1/3 mb-4 md:mb-0">
                        <img id="thumbnail" src="" alt="Miniature" class="w-full rounded">
                    </div>
                    <div class="md:w-2/3 md:pl-6">
                        <h2 id="videoTitle" class="text-xl font-bold mb-2"></h2>
                        <p id="videoUploader" class="text-gray-600 mb-2"></p>
                        <p id="videoDuration" class="text-gray-600"></p>
                    </div>
                </div>
                
                <div class="mb-6">
                    <h3 class="text-lg font-semibold mb-3">Formats disponibles</h3>
                    <div id="formatsList" class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <!-- Formats will be listed here -->
                    </div>
                </div>
            </div>
        </div>
        
        <div class="mt-10 text-center text-gray-500 text-sm">
            <p>© 2025 Youtube Downloader Pro - Utilisez cet outil conformément aux conditions d'utilisation de YouTube</p>
        </div>
    </div>
    
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const urlInput = document.getElementById('url');
            const getInfoBtn = document.getElementById('getInfo');
            const loader = document.getElementById('loader');
            const error = document.getElementById('error');
            const errorMessage = document.getElementById('errorMessage');
            const videoInfo = document.getElementById('videoInfo');
            const thumbnail = document.getElementById('thumbnail');
            const videoTitle = document.getElementById('videoTitle');
            const videoUploader = document.getElementById('videoUploader');
            const videoDuration = document.getElementById('videoDuration');
            const formatsList = document.getElementById('formatsList');
            
            function formatDuration(seconds) {
                const hrs = Math.floor(seconds / 3600);
                const mins = Math.floor((seconds % 3600) / 60);
                const secs = Math.floor(seconds % 60);
                
                let result = '';
                if (hrs > 0) {
                    result += `${hrs}:${mins < 10 ? '0' + mins : mins}:${secs < 10 ? '0' + secs : secs}`;
                } else {
                    result += `${mins}:${secs < 10 ? '0' + secs : secs}`;
                }
                return result;
            }
            
            function formatFileSize(bytes) {
                if (bytes === 0) return '?? MB';
                const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
                const i = Math.floor(Math.log(bytes) / Math.log(1024));
                return parseFloat((bytes / Math.pow(1024, i)).toFixed(2)) + ' ' + sizes[i];
            }
            
            getInfoBtn.addEventListener('click', async function() {
                const url = urlInput.value.trim();
                if (!url) {
                    errorMessage.textContent = 'Veuillez entrer une URL valide';
                    error.classList.remove('hidden');
                    videoInfo.classList.add('hidden');
                    return;
                }
                
                // Hide previous results and errors
                error.classList.add('hidden');
                videoInfo.classList.add('hidden');
                loader.classList.remove('hidden');
                
                try {
                    const response = await fetch('/info', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ url }),
                    });
                    
                    const data = await response.json();
                    
                    if (!response.ok || data.error) {
                        throw new Error(data.error || 'Une erreur est survenue');
                    }
                    
                    // Update video information
                    thumbnail.src = data.thumbnail;
                    videoTitle.textContent = data.title;
                    videoUploader.textContent = `Par ${data.uploader}`;
                    videoDuration.textContent = `Durée: ${formatDuration(data.duration)}`;
                    
                    // Create format buttons
                    formatsList.innerHTML = '';
                    data.formats.forEach(format => {
                        const formatCard = document.createElement('div');
                        formatCard.className = 'border rounded p-4 flex justify-between items-center bg-gray-50 hover:bg-gray-100';
                        
                        const formatInfo = document.createElement('div');
                        
                        const formatTitle = document.createElement('div');
                        formatTitle.className = 'font-medium';
                        formatTitle.textContent = `${format.resolution || 'Audio'} - ${format.ext.toUpperCase()}`;
                        
                        const formatDetails = document.createElement('div');
                        formatDetails.className = 'text-gray-500 text-sm';
                        formatDetails.textContent = `${format.format_note || ''} ${formatFileSize(format.filesize)}`;
                        
                        formatInfo.appendChild(formatTitle);
                        formatInfo.appendChild(formatDetails);
                        
                        const downloadBtn = document.createElement('button');
                        downloadBtn.className = 'bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded text-sm transition-colors';
                        downloadBtn.textContent = 'Télécharger';
                        downloadBtn.addEventListener('click', function() {
                            downloadVideo(url, format.format_id);
                        });
                        
                        formatCard.appendChild(formatInfo);
                        formatCard.appendChild(downloadBtn);
                        formatsList.appendChild(formatCard);
                    });
                    
                    // Show video info
                    videoInfo.classList.remove('hidden');
                    
                } catch (err) {
                    console.error('Error:', err);
                    errorMessage.textContent = err.message || 'Une erreur s\'est produite lors de la récupération des informations';
                    error.classList.remove('hidden');
                } finally {
                    loader.classList.add('hidden');
                }
            });
            
            function downloadVideo(url, formatId) {
                const downloadForm = document.createElement('form');
                downloadForm.method = 'POST';
                downloadForm.action = '/download';
                
                const urlInput = document.createElement('input');
                urlInput.type = 'hidden';
                urlInput.name = 'url';
                urlInput.value = url;
                
                const formatInput = document.createElement('input');
                formatInput.type = 'hidden';
                formatInput.name = 'format_id';
                formatInput.value = formatId;
                
                downloadForm.appendChild(urlInput);
                downloadForm.appendChild(formatInput);
                document.body.appendChild(downloadForm);
                downloadForm.submit();
                document.body.removeChild(downloadForm);
            }
            
            // Allow pressing Enter in the URL field
            urlInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    getInfoBtn.click();
                }
            });
        });
    </script>
</body>
</html>            ''')
    
    # Démarrage du serveur
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

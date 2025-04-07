from flask import Flask, request, send_file, jsonify, render_template
import yt_dlp
import os
import uuid
import time
import random
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Dict, List, Optional
import json
import requests
from urllib.parse import urlparse
import string
import socket
import hashlib
from user_agents import parse
from functools import lru_cache

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

# Cache pour éviter de répéter les mêmes requêtes
@lru_cache(maxsize=100)
def get_user_agent_fingerprint() -> str:
    """Génère un fingerprint basé sur l'agent utilisateur pour la session"""
    agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
    ]
    agent = random.choice(agents)
    parsed_agent = parse(agent)
    
    # Assurer que l'agent semble humain
    if parsed_agent.is_bot or parsed_agent.is_email_client:
        agent = agents[0]  # Utilisez un agent par défaut fiable
    
    return agent

def get_browser_fingerprint() -> Dict:
    """Simule un fingerprint de navigateur cohérent"""
    screen_resolutions = [
        (1920, 1080), (1366, 768), (1440, 900), 
        (1536, 864), (1280, 720), (2560, 1440)
    ]
    screen_width, screen_height = random.choice(screen_resolutions)
    
    return {
        "screen_width": screen_width,
        "screen_height": screen_height,
        "color_depth": random.choice([24, 32]),
        "pixel_ratio": random.choice([1, 1.5, 2, 2.5]),
        "language": random.choice(["en-US", "en-GB", "fr-FR", "es-ES", "de-DE"]),
        "timezone_offset": random.randint(-720, 720),
        "session_storage": True,
        "local_storage": True,
        "indexed_db": True,
        "cpu_cores": random.randint(2, 16),
        "platform": random.choice(["Win32", "MacIntel", "Linux x86_64"]),
        "do_not_track": random.choice(["1", "0", None])
    }

def get_smart_proxy() -> Optional[str]:
    """Système intelligent de gestion des proxies avec vérification de disponibilité"""
    proxy_list = [
        "http://proxy1:8080",
        "http://proxy2:8080",
        "http://proxy3:8080",
        "http://proxy4:8080", 
        "http://proxy5:8080"
    ]
    
    # En environnement de production, remplacez par vos vrais proxies
    # et implémentez une vérification de disponibilité
    
    working_proxies = []
    for proxy in proxy_list:
        try:
            # Test proxy with short timeout
            parsed = urlparse(proxy)
            socket.create_connection((parsed.hostname, parsed.port), timeout=2)
            working_proxies.append(proxy)
        except:
            logger.warning(f"Proxy {proxy} indisponible")
    
    if not working_proxies:
        logger.warning("Aucun proxy disponible, tentative sans proxy")
        return None
    
    return random.choice(working_proxies)

def get_headers(url: str) -> Dict[str, str]:
    """Génère des en-têtes HTTP réalistes basés sur l'URL de destination"""
    user_agent = get_user_agent_fingerprint()
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    
    # En-têtes de base réalistes
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate", 
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache"
    }
    
    # Ajout d'un referer réaliste
    if "youtube" in domain:
        possible_referers = [
            "https://www.google.com/",
            "https://www.facebook.com/",
            "https://twitter.com/",
            f"https://{domain}/results?search_query={generate_random_search()}",
            "https://www.reddit.com/r/videos/",
        ]
        headers["Referer"] = random.choice(possible_referers)
    
    return headers

def generate_random_search() -> str:
    """Génère une recherche aléatoire plausible"""
    words = ["how", "to", "best", "top", "funny", "amazing", "tutorial", 
             "review", "music", "video", "game", "sports", "news"]
    query = " ".join(random.sample(words, random.randint(2, 4)))
    return query

def human_delay(min_seconds=2, max_seconds=5):
    """Simule un délai humain avec microvariations"""
    base_delay = random.uniform(min_seconds, max_seconds)
    # Ajout de micro-pauses aléatoires pour simuler un comportement humain
    micro_pauses = [random.uniform(0.1, 0.5) for _ in range(random.randint(1, 3))]
    
    delay = base_delay + sum(micro_pauses)
    
    # Simuler des interactions utilisateur pendant le délai
    time.sleep(delay * 0.6)  # Premier délai
    
    # Simuler un clic ou une action
    if random.random() > 0.7:
        time.sleep(random.uniform(0.1, 0.3))
    
    time.sleep(delay * 0.4)  # Deuxième délai
    
    logger.info(f"Délai humain simulé: {delay:.2f}s")

def generate_filename(video_title: str, ext: str) -> str:
    """Génère un nom de fichier sécurisé basé sur le titre"""
    # Nettoyer le titre pour un nom de fichier valide
    valid_chars = f"-_.() {string.ascii_letters}{string.digits}"
    safe_title = ''.join(c for c in video_title if c in valid_chars)
    safe_title = safe_title[:50].strip()  # Limiter la longueur
    
    # Ajouter un identifiant unique pour éviter les collisions
    unique_id = hashlib.md5(f"{video_title}{time.time()}".encode()).hexdigest()[:8]
    
    return f"{safe_title}_{unique_id}.{ext}"

def get_download_folder() -> str:
    """Crée et retourne un dossier de téléchargement organisé"""
    folder = os.path.join('downloads', datetime.now().strftime('%Y-%m-%d'))
    os.makedirs(folder, exist_ok=True)
    return folder

def load_cookies() -> Dict:
    """Charge les cookies depuis le fichier ou l'environnement"""
    cookies_env = os.getenv('YOUTUBE_COOKIES')
    if cookies_env:
        try:
            return json.loads(cookies_env)
        except json.JSONDecodeError:
            logger.error("Erreur de décodage des cookies")
    
    # Essayer de charger depuis un fichier
    cookie_file = 'cookies.json'
    if os.path.exists(cookie_file):
        try:
            with open(cookie_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Erreur lors du chargement des cookies: {e}")
    
    return {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/info', methods=['POST'])
def video_info():
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'URL non fournie'}), 400

        url = data['url']
        logger.info(f"Demande d'info pour: {url}")
        
        # Simulation de comportement utilisateur avant la requête
        human_delay(1, 3)
        
        # Configuration avancée pour contourner les détections
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'no_call_home': True,
            'geo_bypass': True,
            'prefer_free_formats': True,
            'extract_flat': "in_playlist",
            'http_headers': get_headers(url),
            'logger': CustomLogger(),
            'socket_timeout': 15,
        }
        
        # Utilisation aléatoire de proxy pour éviter les motifs
        if random.random() > 0.3:  # 70% de chance d'utiliser un proxy
            proxy = get_smart_proxy()
            if proxy:
                ydl_opts['proxy'] = proxy
        
        # Utilisation conditionnelle des cookies
        cookies = load_cookies()
        if cookies:
            cookies_file = f"temp_cookies_{int(time.time())}.json"
            with open(cookies_file, 'w') as f:
                json.dump(cookies, f)
            ydl_opts['cookiefile'] = cookies_file
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Simulation d'interaction utilisateur
                human_delay(1, 3)
                
                formats = [{
                    'format_id': f.get('format_id', ''),
                    'ext': f.get('ext', ''),
                    'resolution': f.get('resolution') or f"{f.get('height', '')}p",
                    'format_note': f.get('format_note', ''),
                    'filesize': f.get('filesize', 0) or f.get('filesize_approx', 0) or 0
                } for f in info.get('formats', []) if f.get('vcodec') != 'none' or f.get('acodec') != 'none']
                
                # Suppression des doublons et tri par qualité
                unique_formats = {}
                for fmt in formats:
                    key = f"{fmt['resolution']}_{fmt['ext']}"
                    if key not in unique_formats or fmt['filesize'] > unique_formats[key]['filesize']:
                        unique_formats[key] = fmt
                
                sorted_formats = sorted(unique_formats.values(), 
                                       key=lambda x: (0 if not x['resolution'] else 
                                                   int(x['resolution'].replace('p', '')) if x['resolution'].replace('p', '').isdigit() else 0), 
                                       reverse=True)
                
                logger.info(f"Extraction réussie pour: {info.get('title', '')}")
                return jsonify({
                    'success': True,
                    'title': info.get('title', ''),
                    'thumbnail': info.get('thumbnail', ''),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', ''),
                    'formats': sorted_formats
                })
        finally:
            # Nettoyage des fichiers temporaires
            if 'cookiefile' in ydl_opts and os.path.exists(ydl_opts['cookiefile']):
                os.remove(ydl_opts['cookiefile'])
    
    except Exception as e:
        logger.error(f"Erreur lors de l'extraction: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/download', methods=['POST'])
def download_video():
    output_path = None
    try:
        data = request.get_json()
        if not data or 'url' not in data or 'format_id' not in data:
            return jsonify({'error': 'URL ou format_id manquant'}), 400

        url = data['url']
        format_id = data['format_id']
        
        # Extraction préalable du titre pour le nom de fichier
        with yt_dlp.YoutubeDL({'quiet': True, 'skip_download': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'video')
        
        # Génération d'un nom de fichier basé sur le titre
        safe_filename = generate_filename(title, 'mp4')
        output_path = os.path.join(get_download_folder(), safe_filename)
        
        logger.info(f"Téléchargement: {title} (format {format_id})")
        
        # Comportement humain
        human_delay(2, 5)
        
        ydl_opts = {
            'format': format_id,
            'outtmpl': output_path,
            'no_call_home': True,
            'geo_bypass': True,
            'prefer_free_formats': True,
            'http_headers': get_headers(url),
            'logger': CustomLogger(),
            'merge_output_format': 'mp4',
            'postprocessors': [{
                'key': 'FFmpegMetadata',
                'add_metadata': True,
            }],
            'fragment_retries': 10,
            'retries': 5,
            'file_access_retries': 3,
            'extractor_retries': 3,
        }
        
        # Utilisation d'un proxy différent du précédent
        proxy = get_smart_proxy()
        if proxy:
            ydl_opts['proxy'] = proxy
        
        # Ajout des cookies
        cookies = load_cookies()
        if cookies:
            cookies_file = f"temp_cookies_{int(time.time())}.json"
            with open(cookies_file, 'w') as f:
                json.dump(cookies, f)
            ydl_opts['cookiefile'] = cookies_file
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Simulation d'interactions humaines pendant le téléchargement
                human_delay(3, 8)
                ydl.download([url])
                
                logger.info(f"Téléchargement terminé: {output_path}")
                
                return send_file(
                    output_path, 
                    as_attachment=True,
                    download_name=safe_filename,
                    mimetype='video/mp4'
                )
        finally:
            # Nettoyage des fichiers temporaires
            if 'cookiefile' in ydl_opts and os.path.exists(ydl_opts['cookiefile']):
                os.remove(ydl_opts['cookiefile'])
                
    except Exception as e:
        logger.error(f"Erreur de téléchargement: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        # Nettoyage conditionnelle du fichier
        if output_path and os.path.exists(output_path):
            try:
                # Option: garder les fichiers plutôt que de les supprimer
                # pour réduire les téléchargements répétés
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
    
    # Fichier de template HTML minimal si manquant
    templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    os.makedirs(templates_dir, exist_ok=True)
    
    index_html = os.path.join(templates_dir, 'index.html')
    if not os.path.exists(index_html):
        with open(index_html, 'w') as f:
            f.write('''
<!DOCTYPE html>
<html>
<head>
    <title>YouTube Downloader</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .container { background: #f9f9f9; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        input, select, button { padding: 10px; margin: 10px 0; width: 100%; }
        button { background: #ff0000; color: white; border: none; cursor: pointer; }
        button:hover { background: #cc0000; }
        #result { margin-top: 20px; }
        .hidden { display: none; }
        .format-item { padding: 5px; margin: 5px 0; background: #eee; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>YouTube Downloader</h1>
        <input type="text" id="url" placeholder="Collez l'URL YouTube ici" />
        <button id="getInfo">Obtenir les informations</button>
        
        <div id="videoInfo" class="hidden">
            <h2 id="videoTitle"></h2>
            <img id="thumbnail" width="320" />
            <p id="duration"></p>
            
            <h3>Formats disponibles</h3>
            <div id="formats"></div>
        </div>
        
        <div id="result"></div>
    </div>

    <script>
        document.getElementById('getInfo').addEventListener('click', async () => {
            const url = document.getElementById('url').value.trim();
            if (!url) return;
            
            document.getElementById('result').innerHTML = 'Chargement...';
            
            try {
                const response = await fetch('/info', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({url})
                });
                
                const data = await response.json();
                
                if (data.success) {
                    document.getElementById('videoTitle').textContent = data.title;
                    document.getElementById('thumbnail').src = data.thumbnail;
                    document.getElementById('duration').textContent = `Durée: ${Math.floor(data.duration / 60)}:${(data.duration % 60).toString().padStart(2, '0')}`;
                    
                    const formatsDiv = document.getElementById('formats');
                    formatsDiv.innerHTML = '';
                    
                    data.formats.forEach(format => {
                        const formatDiv = document.createElement('div');
                        formatDiv.className = 'format-item';
                        formatDiv.innerHTML = `
                            <strong>${format.resolution || 'Audio'} - ${format.ext}</strong>
                            ${format.format_note ? ` (${format.format_note})` : ''}
                            <button class="download-btn" data-format="${format.format_id}">Télécharger</button>
                        `;
                        formatsDiv.appendChild(formatDiv);
                    });
                    
                    document.getElementById('videoInfo').classList.remove('hidden');
                    document.getElementById('result').innerHTML = '';
                    
                    // Ajouter les gestionnaires d'événements
                    document.querySelectorAll('.download-btn').forEach(btn => {
                        btn.addEventListener('click', () => downloadVideo(url, btn.dataset.format));
                    });
                } else {
                    document.getElementById('result').innerHTML = `Erreur: ${data.error}`;
                }
            } catch (error) {
                document.getElementById('result').innerHTML = `Erreur: ${error.message}`;
            }
        });
        
        async function downloadVideo(url, formatId) {
            document.getElementById('result').innerHTML = 'Téléchargement en cours...';
            
            try {
                const response = await fetch('/download', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({url, format_id: formatId})
                });
                
                if (response.ok) {
                    const blob = await response.blob();
                    const downloadUrl = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.style.display = 'none';
                    a.href = downloadUrl;
                    
                    // Get filename from Content-Disposition
                    const contentDisposition = response.headers.get('Content-Disposition');
                    const filenameMatch = contentDisposition && contentDisposition.match(/filename="(.+)"/);
                    const filename = filenameMatch ? filenameMatch[1] : 'video.mp4';
                    
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(downloadUrl);
                    document.getElementById('result').innerHTML = 'Téléchargement terminé!';
                } else {
                    const errorData = await response.json();
                    document.getElementById('result').innerHTML = `Erreur: ${errorData.error}`;
                }
            } catch (error) {
                document.getElementById('result').innerHTML = `Erreur: ${error.message}`;
            }
        }
    </script>
</body>
</html>
            ''')
    
    # Démarrage du serveur
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

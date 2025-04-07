from flask import Flask, request, send_file, jsonify, render_template
import yt_dlp
import os
import uuid
import time
import random
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Dict, Optional
import json
import requests
from urllib.parse import urlparse
import string
import hashlib
import socket

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

# Liste de proxies spécifiée
def get_smart_proxy() -> Optional[str]:
    """Système intelligent de rotation des proxies avec vérification de disponibilité"""
    proxy_list = [
        "http://172.67.181.112:80",
        "http://172.67.0.16:80",
        "http://104.20.75.222:80",
        "http://172.67.68.124:80"
    ]
    
    # Mélanger la liste pour éviter les motifs de requêtes
    random.shuffle(proxy_list)
    
    # Tester les proxies jusqu'à trouver un proxy fonctionnel
    working_proxies = []
    for proxy in proxy_list:
        try:
            # Test simple du proxy avec un timeout court
            parsed = urlparse(proxy)
            socket.create_connection((parsed.hostname, parsed.port), timeout=2)
            working_proxies.append(proxy)
            logger.info(f"Proxy fonctionnel trouvé: {proxy}")
        except:
            logger.warning(f"Proxy non disponible: {proxy}")
    
    if not working_proxies:
        logger.warning("Aucun proxy disponible, utilisation sans proxy")
        return None
    
    # Choisir un proxy aléatoire parmi ceux qui fonctionnent
    selected_proxy = random.choice(working_proxies)
    logger.info(f"Utilisation du proxy: {selected_proxy}")
    return selected_proxy

def get_user_agent() -> str:
    """Fournit un User-Agent réaliste et moderne"""
    agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
        'Mozilla/5.0 (iPad; CPU OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0'
    ]
    return random.choice(agents)

def get_headers(url: str) -> Dict[str, str]:
    """Génère des en-têtes HTTP réalistes basés sur l'URL de destination"""
    user_agent = get_user_agent()
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
        "DNT": "1"
    }
    
    # Ajout d'un referer réaliste
    if "youtube" in domain:
        possible_referers = [
            "https://www.google.com/search?q=youtube+videos",
            "https://www.facebook.com/",
            "https://twitter.com/",
            f"https://{domain}/results?search_query=trending",
            "https://www.reddit.com/r/videos/",
            None  # Parfois pas de referer (accès direct)
        ]
        referer = random.choice(possible_referers)
        if referer:
            headers["Referer"] = referer
    
    return headers

def human_delay(min_seconds=1, max_seconds=3):
    """Simule un délai humain avec variation naturelle"""
    base_delay = random.uniform(min_seconds, max_seconds)
    
    # Ajout de micro-variations pour simuler un comportement plus naturel
    micro_pauses = random.uniform(0.1, 0.5) if random.random() > 0.7 else 0
    
    total_delay = base_delay + micro_pauses
    logger.info(f"Délai simulé: {total_delay:.2f}s")
    time.sleep(total_delay)

def generate_filename(video_title: str, ext: str) -> str:
    """Génère un nom de fichier sécurisé basé sur le titre"""
    # Nettoyer le titre pour un nom de fichier valide
    valid_chars = f"-_.() {string.ascii_letters}{string.digits}"
    safe_title = ''.join(c for c in video_title if c in valid_chars)
    safe_title = safe_title[:50].strip()  # Limiter la longueur
    
    # Ajouter un identifiant unique
    unique_id = hashlib.md5(f"{video_title}{time.time()}".encode()).hexdigest()[:6]
    
    return f"{safe_title}_{unique_id}.{ext}"

def get_download_folder() -> str:
    """Crée et retourne un dossier de téléchargement organisé"""
    folder = os.path.join('downloads', datetime.now().strftime('%Y-%m-%d'))
    os.makedirs(folder, exist_ok=True)
    return folder

def create_temp_cookie_file() -> Optional[str]:
    """Crée un fichier de cookies temporaire au format txt si disponible"""
    # Vérifier si nous avons un fichier de cookies
    cookie_path = os.getenv('COOKIE_PATH', 'cookies.txt')
    
    if os.path.exists(cookie_path):
        # Créer une copie temporaire
        temp_file = f"temp_cookies_{int(time.time())}.txt"
        try:
            with open(cookie_path, 'r') as src, open(temp_file, 'w') as dest:
                dest.write(src.read())
            logger.info(f"Fichier de cookies temporaire créé: {temp_file}")
            return temp_file
        except Exception as e:
            logger.error(f"Erreur lors de la création du fichier de cookies temporaire: {e}")
    else:
        logger.warning(f"Fichier de cookies introuvable: {cookie_path}")
    
    return None

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
        human_delay(1, 3)
        
        # Configuration optimisée pour contourner les détections
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'no_call_home': True,
            'geo_bypass': True,
            'prefer_free_formats': True,
            'http_headers': get_headers(url),
            'logger': CustomLogger(),
            'socket_timeout': 20,
            'retries': 5,
        }
        
        # Utilisation du proxy
        proxy = get_smart_proxy()
        if proxy:
            ydl_opts['proxy'] = proxy
        
        # Utilisation des cookies au format txt
        temp_cookie_file = create_temp_cookie_file()
        if temp_cookie_file:
            ydl_opts['cookiefile'] = temp_cookie_file
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Simulation d'interaction utilisateur
                human_delay(1, 2)
                
                # Traitement des formats
                formats = [{
                    'format_id': f.get('format_id', ''),
                    'ext': f.get('ext', ''),
                    'resolution': f.get('resolution') or (f"{f.get('height', '')}p" if f.get('height') else ''),
                    'format_note': f.get('format_note', ''),
                    'filesize': f.get('filesize', 0) or f.get('filesize_approx', 0) or 0
                } for f in info.get('formats', []) if f.get('vcodec') != 'none' or f.get('acodec') != 'none']
                
                # Filtrage et tri des formats
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
        except Exception as e:
            logger.error(f"Erreur d'extraction: {str(e)}")
            return jsonify({'error': f"Erreur lors de l'extraction: {str(e)}"}), 500
        finally:
            # Nettoyage
            if temp_cookie_file and os.path.exists(temp_cookie_file):
                try:
                    os.remove(temp_cookie_file)
                except Exception as e:
                    logger.error(f"Erreur lors de la suppression du fichier cookie temporaire: {e}")
    
    except Exception as e:
        logger.error(f"Erreur générale: {str(e)}")
        return jsonify({'error': str(e)}), 500

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
        
        # Configuration pour le téléchargement
        ydl_opts = {
            'format': format_id,
            'outtmpl': output_path,
            'no_call_home': True,
            'geo_bypass': True,
            'http_headers': get_headers(url),
            'logger': CustomLogger(),
            'merge_output_format': 'mp4',
            'postprocessors': [{
                'key': 'FFmpegMetadata',
                'add_metadata': True,
            }],
            'fragment_retries': 10,
            'retries': 5
        }
        
        # Utilisation d'un proxy différent
        proxy = get_smart_proxy()
        if proxy:
            ydl_opts['proxy'] = proxy
        
        # Cookies au format txt
        temp_cookie_file = create_temp_cookie_file()
        if temp_cookie_file:
            ydl_opts['cookiefile'] = temp_cookie_file
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Simulation d'interactions humaines pendant le téléchargement
                human_delay(2, 4)
                ydl.download([url])
                
                logger.info(f"Téléchargement terminé: {output_path}")
                
                # Envoyer le fichier
                return send_file(
                    output_path, 
                    as_attachment=True,
                    download_name=safe_filename,
                    mimetype='video/mp4'
                )
        finally:
            # Nettoyage des fichiers temporaires
            if temp_cookie_file and os.path.exists(temp_cookie_file):
                try:
                    os.remove(temp_cookie_file)
                except:
                    pass
                
    except Exception as e:
        logger.error(f"Erreur de téléchargement: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        # Nettoyage conditionnelle du fichier
        if output_path and os.path.exists(output_path):
            try:
                # Option: garder les fichiers plutôt que de les supprimer
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
        .format-item { padding: 5px; margin: 5px 0; background: #eee; border-radius: 4px; display: flex; justify-content: space-between; align-items: center; }
        .format-info { flex: 1; }
        .format-btn { width: auto; }
        .loader { border: 4px solid #f3f3f3; border-top: 4px solid #ff0000; border-radius: 50%; width: 20px; height: 20px; animation: spin 2s linear infinite; display: inline-block; margin-left: 10px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
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
            
            const resultDiv = document.getElementById('result');
            resultDiv.innerHTML = 'Chargement... <div class="loader"></div>';
            
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
                    
                    // Formater la durée correctement
                    const minutes = Math.floor(data.duration / 60);
                    const seconds = (data.duration % 60).toString().padStart(2, '0');
                    document.getElementById('duration').textContent = `Durée: ${minutes}:${seconds}`;
                    
                    const formatsDiv = document.getElementById('formats');
                    formatsDiv.innerHTML = '';
                    
                    // Afficher les formats disponibles
                    data.formats.forEach(format => {
                        const formatDiv = document.createElement('div');
                        formatDiv.className = 'format-item';
                        
                        // Calculer la taille en MB
                        const sizeMB = format.filesize > 0 ? (format.filesize / (1024 * 1024)).toFixed(1) + ' MB' : 'Taille inconnue';
                        
                        formatDiv.innerHTML = `
                            <div class="format-info">
                                <strong>${format.resolution || 'Audio'} - ${format.ext}</strong>
                                ${format.format_note ? ` (${format.format_note})` : ''}
                                <br>
                                <small>${sizeMB}</small>
                            </div>
                            <button class="download-btn format-btn" data-format="${format.format_id}">Télécharger</button>
                        `;
                        formatsDiv.appendChild(formatDiv);
                    });
                    
                    document.getElementById('videoInfo').classList.remove('hidden');
                    resultDiv.innerHTML = '';
                    
                    // Ajouter les gestionnaires d'événements
                    document.querySelectorAll('.download-btn').forEach(btn => {
                        btn.addEventListener('click', () => downloadVideo(url, btn.dataset.format));
                    });
                } else {
                    resultDiv.innerHTML = `Erreur: ${data.error}`;
                }
            } catch (error) {
                resultDiv.innerHTML = `Erreur: ${error.message}`;
            }
        });
        
        async function downloadVideo(url, formatId) {
            const resultDiv = document.getElementById('result');
            resultDiv.innerHTML = 'Téléchargement en cours... <div class="loader"></div>';
            resultDiv.scrollIntoView({ behavior: 'smooth' });
            
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
                    resultDiv.innerHTML = '<span style="color: green">✓ Téléchargement terminé!</span>';
                    
                    // Nettoyer l'élément après quelques secondes
                    setTimeout(() => {
                        resultDiv.innerHTML = '';
                    }, 5000);
                } else {
                    const errorData = await response.json();
                    resultDiv.innerHTML = `<span style="color: red">Erreur: ${errorData.error}</span>`;
                }
            } catch (error) {
                resultDiv.innerHTML = `<span style="color: red">Erreur: ${error.message}</span>`;
            }
        }
    </script>
</body>
</html>
            ''')
    
    # Démarrage du serveur
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

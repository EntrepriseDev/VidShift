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

# Configuration améliorée
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB limite
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
TEMP_DIR = tempfile.gettempdir()

# Créer le répertoire templates s'il n'existe pas
templates_dir = Path(os.path.dirname(os.path.abspath(__file__))) / 'templates'
templates_dir.mkdir(exist_ok=True)

# Créer le fichier index.html dans le répertoire templates
index_html_path = templates_dir / 'index.html'
if not index_html_path.exists():
    with open(index_html_path, 'w', encoding='utf-8') as f:
        f.write('''<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YouTube Downloader Pro</title>
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            max-width: 800px; 
            margin: 0 auto; 
            padding: 20px; 
            background: #f9f9f9; 
            color: #333; 
        }
        h1 { 
            color: #ff0000; 
            text-align: center; 
        }
        input, button, select { 
            padding: 12px; 
            margin: 10px 0; 
            width: 100%; 
            box-sizing: border-box; 
            border-radius: 4px; 
            border: 1px solid #ddd; 
        }
        button { 
            background: #ff0000; 
            color: white; 
            border: none; 
            cursor: pointer; 
            font-weight: bold; 
            transition: all 0.3s; 
        }
        button:hover { 
            background: #cc0000; 
        }
        #formats { 
            margin-top: 20px; 
            background: white; 
            padding: 15px; 
            border-radius: 8px; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
        }
        #result { 
            margin-top: 20px; 
            padding: 15px; 
            border-radius: 8px; 
            background: #f0f0f0; 
            text-align: center; 
        }
        .hidden { 
            display: none; 
        }
        .thumbnail { 
            display: block; 
            margin: 10px auto; 
            border-radius: 5px; 
            max-width: 300px;
        }
        .loading { 
            display: inline-block; 
            width: 20px; 
            height: 20px; 
            border: 3px solid rgba(255,0,0,.3); 
            border-radius: 50%; 
            border-top-color: #ff0000; 
            animation: spin 1s ease-in-out infinite; 
            margin-right: 10px; 
            vertical-align: middle; 
        }
        @keyframes spin { 
            to { transform: rotate(360deg); } 
        }
        .format-option { 
            margin: 5px 0; 
            padding: 8px; 
            background: #f9f9f9; 
            border-radius: 4px; 
        }
        select { 
            background: #fff; 
        }
    </style>
</head>
<body>
    <h1>YouTube Downloader Pro</h1>
    <div>
        <input type="text" id="url" placeholder="Coller l'URL de la vidéo YouTube ici...">
        <button onclick="getInfo()">Analyser<span id="analyze-spinner" class="loading hidden"></span></button>
    </div>
    <div id="formats" class="hidden"></div>
    <div id="result" class="hidden"></div>
    <script>
        // Ajout d'un délai aléatoire pour simuler un comportement humain
        function humanDelay(callback) {
            setTimeout(callback, Math.random() * 300 + 100);
        }
        
        async function getInfo() {
            const url = document.getElementById('url').value.trim();
            if (!url) return;
            
            // Afficher le spinner
            document.getElementById('analyze-spinner').classList.remove('hidden');
            document.getElementById('formats').classList.add('hidden');
            document.getElementById('result').classList.add('hidden');
            
            try {
                // Attendre un peu avant d'envoyer pour simuler un humain
                await new Promise(r => setTimeout(r, Math.random() * 700 + 300));
                
                const response = await fetch('/info', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({url, timestamp: Date.now()})
                });
                
                const data = await response.json();
                if (data.error) throw new Error(data.error);
                
                humanDelay(() => {
                    document.getElementById('formats').innerHTML = `
                        <h2>${data.title}</h2>
                        ${data.thumbnail ? `<img src="${data.thumbnail}" class="thumbnail">` : ''}
                        <p>Durée: ${Math.floor(data.duration / 60)}:${String(data.duration % 60).padStart(2, '0')}</p>
                        <h3>Formats disponibles:</h3>
                        <select id="format_selector">
                            ${data.formats.map(f => 
                                `<option value="${f.format_id}">${f.resolution || f.format_note} (${f.ext}) - ${Math.round(f.filesize/1024/1024 || 0)}MB</option>`
                            ).join('')}
                        </select>
                        <button onclick="downloadVideo()">Télécharger<span id="download-spinner" class="loading hidden"></span></button>
                    `;
                    document.getElementById('formats').classList.remove('hidden');
                    document.getElementById('analyze-spinner').classList.add('hidden');
                });
            } catch (error) {
                document.getElementById('analyze-spinner').classList.add('hidden');
                document.getElementById('result').innerHTML = `Erreur: ${error.message}`;
                document.getElementById('result').classList.remove('hidden');
            }
        }
        
        async function downloadVideo() {
            const url = document.getElementById('url').value;
            const format_id = document.getElementById('format_selector').value;
            
            document.getElementById('download-spinner').classList.remove('hidden');
            document.getElementById('result').innerHTML = 'Téléchargement en cours...';
            document.getElementById('result').classList.remove('hidden');
            
            try {
                // Simuler une interaction humaine avec un léger délai
                await new Promise(r => setTimeout(r, Math.random() * 500 + 200));
                
                const response = await fetch('/download', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        url, 
                        format_id,
                        timestamp: Date.now(),
                        client_id: Math.random().toString(36).substring(2, 15)
                    })
                });
                
                if (response.ok) {
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = response.headers.get('Content-Disposition')?.split('filename=')[1]?.replace(/"/g, '') || 'video.mp4';
                    document.body.appendChild(a);
                    
                    // Léger délai avant de cliquer pour simuler un comportement humain
                    setTimeout(() => {
                        a.click();
                        window.URL.revokeObjectURL(url);
                        document.getElementById('download-spinner').classList.add('hidden');
                        document.getElementById('result').innerHTML = 'Téléchargement terminé!';
                    }, Math.random() * 300 + 100);
                } else {
                    const error = await response.json();
                    document.getElementById('download-spinner').classList.add('hidden');
                    document.getElementById('result').innerHTML = `Erreur: ${error.error}`;
                }
            } catch (error) {
                document.getElementById('download-spinner').classList.add('hidden');
                document.getElementById('result').innerHTML = `Erreur: ${error.message}`;
            }
        }
        
        // Ajouter un écouteur pour l'appui sur Entrée dans le champ URL
        document.getElementById('url').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                getInfo();
            }
        });
    </script>
</body>
</html>''')

# User agents réalistes - Optimisés et mis à jour
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1'
]

# Fonction pour obtenir un user-agent aléatoire - Optimisée
def get_random_user_agent():
    return random.choice(USER_AGENTS)

# Middleware de sécurité
@app.after_request
def add_security_headers(response):
    response.headers.update({
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'Content-Security-Policy': "default-src 'self'; img-src 'self' i.ytimg.com *.googleusercontent.com data:; script-src 'self' 'unsafe-inline';"
    })
    return response

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

# Fonction pour générer un fichier de cookies YouTube valide - Optimisée avec Path
def ensure_valid_cookie():
    cookie_path = Path(os.path.dirname(os.path.abspath(__file__))) / 'cookies.txt'
    
    # Si le fichier de cookies n'existe pas ou est vide, on crée un fichier basique
    if not cookie_path.exists() or cookie_path.stat().st_size == 0:
        try:
            # Génération d'un cookie de consentement YouTube minimal
            with open(cookie_path, 'w') as f:
                f.write("""# Netscape HTTP Cookie File
.youtube.com\tTRUE\t/\tFALSE\t2147483647\tCONSENT\tYES+cb.20210328-17-p0.en-GB+FX+{0}
.youtube.com\tTRUE\t/\tFALSE\t2147483647\tVISITOR_INFO1_LIVE\t{1}
.youtube.com\tTRUE\t/\tFALSE\t2147483647\tPREF\tid=f1&tz=Europe%2FParis&f6=40000000&f5=30000
.youtube.com\tTRUE\t/\tFALSE\t2147483647\tYSC\t{2}
""".format(
                    random.randint(100, 999),
                    ''.join(random.choices('0123456789ABCDEFabcdef', k=16)),
                    ''.join(random.choices('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz', k=11))
                ))
            logger.info("Fichier de cookies créé avec succès")
        except Exception as e:
            logger.error(f"Erreur lors de la création du fichier de cookies: {str(e)}")
    
    return str(cookie_path)

# Extraire l'ID vidéo YouTube d'une URL - Méthode optimisée et plus robuste
def extract_video_id(url):
    # Pattern consolidé pour les URLs YouTube
    pattern = r'(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/|youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})'
    
    match = re.search(pattern, url)
    return match.group(1) if match else None

# Page d'accueil - Simplifiée pour utiliser directement le template
@app.route('/')
def index():
    return render_template('index.html')

# Obtenir les informations de la vidéo - Optimisé
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
        user_agent = get_random_user_agent()
        
        # Options améliorées et optimisées
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'format': 'best',
            'extractor_args': {
                'youtube': {
                    'skip': ['dash', 'hls'],
                    'player_client': ['web', 'android'],
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
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
                'Origin': 'https://www.youtube.com',
                'Referer': f'https://www.youtube.com/watch?v={video_id}'
            },
            'socket_timeout': 15,
            'source_address': '0.0.0.0',
            'sleep_interval': random.randint(1, 3),
            'max_sleep_interval': 5
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
        else:
            return jsonify({'error': 'Erreur lors de l\'extraction des informations. Veuillez réessayer.'}), 500

# Télécharger la vidéo - Optimisé
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
        user_agent = get_random_user_agent()
        
        # Ajout d'un délai aléatoire pour simuler un comportement humain
        time.sleep(random.uniform(1.0, 2.5))
        
        # Options de téléchargement optimisées
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
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
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
                }
            }
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'video').replace('/', '_').replace('\\', '_')
            extension = info.get('ext', 'mp4')
            
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
        else:
            return jsonify({'error': 'Erreur lors du téléchargement. Veuillez réessayer.'}), 500

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
    
    # Démarrer le serveur
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

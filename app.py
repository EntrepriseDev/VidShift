from flask import Flask, request, send_file, jsonify, render_template, Response
import yt_dlp
import os
import uuid
import tempfile
import logging
from functools import wraps
import time

# Configuration avancée
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB limite
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
TEMP_DIR = tempfile.gettempdir()

# Middleware de sécurité
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Content-Security-Policy'] = "default-src 'self'"
    return response

# Rate limiting basique
def rate_limit(limit=5, per=60):
    ips = {}
    
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            ip = request.remote_addr
            now = time.time()
            
            # Nettoyer les anciennes requêtes
            if ip in ips:
                ips[ip] = [r for r in ips[ip] if now - r < per]
            
            # Vérifier la limite
            if ip in ips and len(ips[ip]) >= limit:
                return jsonify({"error": "Rate limit exceeded"}), 429
            
            # Ajouter cette requête
            if ip not in ips:
                ips[ip] = []
            ips[ip].append(now)
            
            return f(*args, **kwargs)
        return wrapped
    return decorator

# Page d'accueil
@app.route('/')
def index():
    try:
        return render_template('index.html')
    except:
        logger.warning("Template index.html non trouvé. Utilisation du template de secours.")
        return Response('''
        <!DOCTYPE html>
        <html lang="fr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>YouTube Downloader</title>
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
                input, button, select { padding: 10px; margin: 10px 0; width: 100%; box-sizing: border-box; }
                button { background: #f00; color: white; border: none; cursor: pointer; }
                #formats { margin-top: 20px; }
                #result { margin-top: 20px; }
                .hidden { display: none; }
            </style>
        </head>
        <body>
            <h1>YouTube Downloader</h1>
            <div>
                <input type="text" id="url" placeholder="URL de la vidéo YouTube">
                <button onclick="getInfo()">Obtenir les formats</button>
            </div>
            <div id="formats" class="hidden"></div>
            <div id="result" class="hidden"></div>
            <script>
                async function getInfo() {
                    const url = document.getElementById('url').value;
                    if (!url) return;
                    
                    try {
                        const response = await fetch('/info', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({url})
                        });
                        
                        const data = await response.json();
                        if (data.error) throw new Error(data.error);
                        
                        document.getElementById('formats').innerHTML = `
                            <h2>${data.title}</h2>
                            ${data.thumbnail ? `<img src="${data.thumbnail}" style="max-width:300px">` : ''}
                            <p>Durée: ${Math.floor(data.duration / 60)}:${String(data.duration % 60).padStart(2, '0')}</p>
                            <h3>Formats disponibles:</h3>
                            <select id="format_selector">
                                ${data.formats.map(f => `<option value="${f.format_id}">${f.resolution || f.format_note} (${f.ext}) - ${Math.round(f.filesize/1024/1024 || 0)}MB</option>`).join('')}
                            </select>
                            <button onclick="downloadVideo()">Télécharger</button>
                        `;
                        document.getElementById('formats').classList.remove('hidden');
                    } catch (error) {
                        alert('Erreur: ' + error.message);
                    }
                }
                
                async function downloadVideo() {
                    const url = document.getElementById('url').value;
                    const format_id = document.getElementById('format_selector').value;
                    
                    document.getElementById('result').innerHTML = 'Téléchargement en cours...';
                    document.getElementById('result').classList.remove('hidden');
                    
                    const response = await fetch('/download', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({url, format_id})
                    });
                    
                    if (response.ok) {
                        const blob = await response.blob();
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = 'video.mp4';
                        document.body.appendChild(a);
                        a.click();
                        window.URL.revokeObjectURL(url);
                        document.getElementById('result').innerHTML = 'Téléchargement terminé!';
                    } else {
                        const error = await response.json();
                        document.getElementById('result').innerHTML = `Erreur: ${error.error}`;
                    }
                }
            </script>
        </body>
        </html>
        ''', content_type='text/html')

# Obtenir les informations de la vidéo
@app.route('/info', methods=['POST'])
@rate_limit()
def video_info():
    try:
        data = request.json
        url = data.get('url')
        
        if not url:
            return jsonify({'error': 'Aucune URL fournie'}), 400
        
        # Configuration avancée pour contourner les limitations
        ydl_opts = {
            'quiet': True, 
            'skip_download': True,
            'format': 'best',
            'extractor_args': {'youtube': {'skip': ['dash', 'hls']}},
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'geo_bypass': True,
            'cookiefile': os.path.join(os.path.dirname(__file__), 'cookies.txt')
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Filtrer et trier les formats par qualité
            formats = [
                {
                    'format_id': f['format_id'],
                    'ext': f['ext'],
                    'resolution': f.get('resolution') or f"{f.get('height', '')}p",
                    'format_note': f.get('format_note', ''),
                    'filesize': f.get('filesize') or f.get('filesize_approx', 0)
                } 
                for f in info.get('formats', []) 
                if f.get('vcodec') != 'none' or f.get('acodec') != 'none'
            ]
            
            # Trier par taille de fichier décroissante
            formats.sort(key=lambda x: x['filesize'], reverse=True)
            
            return jsonify({
                'title': info['title'],
                'thumbnail': info.get('thumbnail', ''),
                'duration': info['duration'],
                'formats': formats[:10]  # Limiter aux 10 meilleurs formats
            })
    except Exception as e:
        logger.error(f"Erreur lors de l'extraction des infos: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Télécharger la vidéo
@app.route('/download', methods=['POST'])
@rate_limit(limit=2, per=300)  # Limite plus stricte pour les téléchargements
def download_video():
    try:
        data = request.json
        url = data.get('url')
        format_id = data.get('format_id')
        
        if not url or not format_id:
            return jsonify({'error': 'URL ou format manquant'}), 400
        
        # Créer un nom de fichier unique dans le répertoire temporaire
        filename = f"video_{uuid.uuid4().hex}.mp4"
        output_path = os.path.join(TEMP_DIR, filename)
        
        ydl_opts = {
            'format': format_id,
            'outtmpl': output_path,
            'nocheckcertificate': True,
            'geo_bypass': True,
            'cookiefile': os.path.join(os.path.dirname(__file__), 'cookies.txt')
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'video').replace('/', '_').replace('\\', '_')
            
        # Envoyer le fichier avec le nom de la vidéo et supprimer après envoi
        response = send_file(
            output_path, 
            as_attachment=True, 
            download_name=f"{title}.{info.get('ext', 'mp4')}"
        )
        
        # Supprimer le fichier après un court délai
        @response.call_on_close
        def cleanup():
            try:
                if os.path.exists(output_path):
                    os.remove(output_path)
            except:
                pass
                
        return response
    except Exception as e:
        logger.error(f"Erreur de téléchargement: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Configuration pour Render
if __name__ == '__main__':
    # Créer le fichier cookies vide si nécessaire
    cookie_path = os.path.join(os.path.dirname(__file__), 'cookies.txt')
    if not os.path.exists(cookie_path):
        with open(cookie_path, 'w') as f:
            pass
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

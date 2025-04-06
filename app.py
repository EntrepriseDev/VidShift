from flask import Flask, request, send_file, jsonify, render_template
import yt_dlp
import os
import uuid
import time
import random

app = Flask(__name__)

# Logger personnalisé
class CustomLogger:
    def debug(self, msg):
        pass
    
    def warning(self, msg):
        pass
    
    def error(self, msg):
        pass

# Fonction pour obtenir un user-agent aléatoire
def get_random_user_agent():
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 11_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0'
    ]
    return {'User-Agent': random.choice(user_agents)}

# Fonction pour obtenir un proxy aléatoire
def get_proxy():
    proxies = {
        'http': 'http://proxy1:8080',
        'https': 'http://proxy1:8080'
    }
    # Rotation des proxies toutes les heures
    if random.randint(0, 100) < 10:  # 10% de chance de changer de proxy
        proxies['http'] = f'http://proxy{random.randint(1, 5)}:8080'
        proxies['https'] = f'http://proxy{random.randint(1, 5)}:8080'
    return proxies

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/info', methods=['POST'])
def video_info():
    try:
        # Récupération des données de la requête
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'No URL provided'}), 400
        url = data['url']

        # Options de yt-dlp
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'no_call_home': True,
            'geo_bypass': True,
            'prefer_free_formats': True,
            'user_agent': get_random_user_agent(),
            'proxy': get_proxy(),
            'logger': CustomLogger()
        }
        
        # Extraction des informations de la vidéo
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            # Traitement des formats vidéo
            formats = [{
                'format_id': f['format_id'],
                'ext': f['ext'],
                'resolution': f.get('resolution') or f.get('height', ''),
                'format_note': f.get('format_note', ''),
                'filesize': f.get('filesize') or 0
            } for f in info.get('formats', []) if f.get('vcodec') != 'none' or f.get('acodec') != 'none']
            
            # Simulation d'un délai pour un comportement humain
            time.sleep(random.randint(1, 3))
            
            # Réponse avec les informations de la vidéo
            return jsonify({
                'title': info['title'],
                'thumbnail': info['thumbnail'],
                'duration': info['duration'],
                'formats': formats
            })
    except Exception as e:
        # Gestion des erreurs
        return jsonify({'error': str(e)}), 500

@app.route('/download', methods=['POST'])
def download_video():
    try:
        # Récupération des données de la requête
        data = request.get_json()
        if not data or 'url' not in data or 'format_id' not in data:
            return jsonify({'error': 'Missing URL or format_id'}), 400

        url = data['url']
        format_id = data['format_id']

        # Création du nom de fichier et du chemin de téléchargement
        filename = f"video_{uuid.uuid4().hex}.mp4"
        output_path = os.path.join("downloads", filename)

        # Options de yt-dlp pour télécharger la vidéo
        ydl_opts = {
            'format': format_id,
            'outtmpl': output_path,
            'no_call_home': True,
            'geo_bypass': True,
            'prefer_free_formats': True,
            'user_agent': get_random_user_agent(),
            'proxy': get_proxy(),
            'logger': CustomLogger()
        }

        # Téléchargement de la vidéo
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            time.sleep(random.randint(2, 5))  # Ajout d'un délai avant le téléchargement
            ydl.download([url])
            
            # Envoi du fichier téléchargé
            return send_file(output_path, as_attachment=True)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    finally:
        # Nettoyage après téléchargement (suppression du fichier téléchargé)
        if os.path.exists(output_path):
            os.remove(output_path)

if __name__ == '__main__':
    os.makedirs('downloads', exist_ok=True)  # Création du dossier pour les téléchargements
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))

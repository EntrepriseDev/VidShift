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

class CustomLogger:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        handler = RotatingFileHandler('app.log', maxBytes=1_000_000, backupCount=3)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def debug(self, msg):
        self.logger.debug(msg)
    
    def warning(self, msg):
        self.logger.warning(msg)
    
    def error(self, msg):
        self.logger.error(msg)
        
    def info(self, msg):
        self.logger.info(msg)

logger = CustomLogger()

# Cache pour les informations vidéo avec gestion thread-safe
video_cache = {}
cache_lock = threading.Lock()

def get_user_agent() -> str:
    """Génère un User-Agent aléatoire et moderne"""
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
    """Système optimisé de sélection de proxy avec gestion des erreurs"""
    proxy_list = [
        "http://172.67.181.112:80",
        "http://172.67.0.16:80",
        "http://104.20.75.222:80",
        "http://172.67.68.124:80",
        "http://203.24.108.86:80",
        "http://203.23.104.223:80"
    ]
    
    custom_proxies = os.getenv('CUSTOM_PROXIES')
    if custom_proxies:
        try:
            additional_proxies = json.loads(custom_proxies)
            if isinstance(additional_proxies, list):
                proxy_list.extend(additional_proxies)
        except json.JSONDecodeError:
            logger.error(f"Erreur de parsing des proxies personnalisés: {custom_proxies}")
    
    random.shuffle(proxy_list)
    
    cache_file = os.path.join(tempfile.gettempdir(), "working_proxies.json")
    if os.path.exists(cache_file):
        try:
            if (time.time() - os.path.getmtime(cache_file)) < 43200:
                with open(cache_file, 'r') as f:
                    working_proxies = json.load(f)
                if working_proxies:
                    return random.choice(working_proxies)
        except Exception as e:
            logger.error(f"Erreur lecture fichier cache: {str(e)}")
    
    working_proxies = []
    test_proxies = random.sample(proxy_list, min(3, len(proxy_list)))
    
    for proxy in test_proxies:
        try:
            response = requests.get(
                "https://www.youtube.com",
                proxies={"http": proxy, "https": proxy},
                headers={"User-Agent": get_user_agent()},
                timeout=3
            )
            if response.status_code == 200:
                working_proxies.append(proxy)
                logger.info(f"Proxy fonctionnel détecté: {proxy}")
        except requests.RequestException as e:
            logger.error(f"Erreur test proxy {proxy}: {str(e)}")
    
    if working_proxies:
        try:
            with open(cache_file, 'w') as f:
                json.dump(working_proxies, f)
        except Exception as e:
            logger.error(f"Erreur écriture cache proxies: {str(e)}")
        return random.choice(working_proxies)
    
    logger.warning("Aucun proxy disponible")
    return None

def get_headers(url: str) -> Dict[str, str]:
    """Génère des en-têtes HTTP réalistes basés sur l'URL"""
    user_agent = get_user_agent()
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    
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
    
    if "youtube" in domain:
        referer_options = [
            "https://www.google.com/search?q=youtube+videos",
            f"https://{domain}/results?search_query=trending",
            "https://www.reddit.com/r/videos/",
            None
        ]
        headers["Referer"] = random.choice(referer_options)
    
    return headers

def delay(min_time=0.5, max_time=2.0):
    """Simule un délai humain naturel"""
    time.sleep(random.uniform(min_time, max_time))

@app.route('/info', methods=['POST'])
def video_info():
    temp_cookie_file = None
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'URL non fournie'}), 400

        url = data['url']
        logger.info(f"Demande d'info pour: {url}")
        
        delay(1, 2)
        
        video_id = extract_video_id(url)
        if video_id:
            with cache_lock:
                if video_id in video_cache and time.time() - video_cache[video_id]['timestamp'] < 3600:
                    logger.info(f"Utilisation du cache pour {video_id}")
                    return jsonify(video_cache[video_id]['data'])

        processed_url = preprocess_url(url)
        
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'no_call_home': True,
            'geo_bypass': True,
            'http_headers': get_headers(processed_url),
            'logger': logger,
            'socket_timeout': 20,
            'retries': 5,
            'nocheckcertificate': True,
            
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
            
            'dynamic_mpd': True,
            'throttled_rate': '100K',
            'concurrent_fragment_downloads': 1,
        }
        
        proxy = get_proxy()
        if proxy:
            ydl_opts['proxy'] = proxy
        
        temp_cookie_file = create_cookie_file()
        if temp_cookie_file:
            ydl_opts['cookiefile'] = temp_cookie_file
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                delay(0.5, 1.5)
                
                info = ydl.extract_info(processed_url, download=False)
                
                formats = [{
                    'format_id': f.get('format_id', ''),
                    'ext': f.get('ext', ''),
                    'resolution': f.get('resolution') or (f"{f.get('height', '')}p" if f.get('height') else ''),
                    'format_note': f.get('format_note', ''),
                    'filesize': f.get('filesize', 0) or f.get('filesize_approx', 0) or 0,
                    'vcodec': f.get('vcodec', ''),
                    'acodec': f.get('acodec', '')
                } for f in info.get('formats', []) if not (f.get('vcodec') == 'none' and f.get('acodec') == 'none')]
                
                unique_formats = {}
                for fmt in formats:
                    key = f"{fmt['resolution']}_{fmt['ext']}"
                    if key not in unique_formats or fmt['filesize'] > unique_formats[key]['filesize']:
                        unique_formats[key] = fmt
                
                sorted_formats = sorted(
                    unique_formats.values(), 
                    key=lambda x: (0 if not x['resolution'] else 
                                  int(x['resolution'].replace('p', '')) if x['resolution'].replace('p', '').isdigit() else 0), 
                    reverse=True
                )
                
                response_data = {
                    'success': True,
                    'title': info.get('title', ''),
                    'thumbnail': info.get('thumbnail', ''),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', ''),
                    'formats': sorted_formats
                }
                
                if video_id:
                    with cache_lock:
                        video_cache[video_id] = {
                            'timestamp': time.time(),
                            'data': response_data
                        }
                
                logger.info(f"Extraction réussie: {info.get('title', '')}")
                return jsonify(response_data)
                
        except Exception as e:
            logger.error(f"Erreur d'extraction: {str(e)}")
            return jsonify({'error': f"Erreur lors de l'extraction: {str(e)}"}), 500
        
    finally:
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
        
        processed_url = preprocess_url(url)
        
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'skip_download': True}) as ydl:
                info = ydl.extract_info(processed_url, download=False)
                title = info.get('title', 'video')
        except Exception as e:
            logger.error(f"Erreur extraction titre: {str(e)}")
            title = f"youtube_video_{int(time.time())}"
        
        safe_filename = generate_filename(title, 'mp4')
        output_path = os.path.join(get_download_folder(), safe_filename)
        
        logger.info(f"Téléchargement: {title} (format {format_id})")
        
        delay(1, 3)
        
        ydl_opts = {
            'format': format_id,
            'outtmpl': output_path,
            'no_call_home': True,
            'geo_bypass': True,
            'http_headers': get_headers(processed_url),
            'logger': logger,
            'merge_output_format': 'mp4',
            'fragment_retries': 10,
            'retries': 5,
            'nocheckcertificate': True,
            
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
            
            'postprocessors': [{
                'key': 'FFmpegMetadata',
                'add_metadata': True,
            }],
            
            'throttled_rate': '512K',
            'concurrent_fragment_downloads': 2,
            'dynamic_mpd': True,
        }
        
        proxy = get_proxy()
        if proxy:
            ydl_opts['proxy'] = proxy
        
        temp_cookie_file = create_cookie_file()
        if temp_cookie_file:
            ydl_opts['cookiefile'] = temp_cookie_file
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                delay(1, 2)
                
                ydl.download([processed_url])
                
                logger.info(f"Téléchargement terminé: {output_path}")
                
                return send_file(
                    output_path, 
                    as_attachment=True,
                    download_name=safe_filename,
                    mimetype='video/mp4'
                )
        finally:
            if temp_cookie_file and os.path.exists(temp_cookie_file):
                try:
                    os.remove(temp_cookie_file)
                except:
                    pass
    except Exception as e:
        logger.error(f"Erreur de téléchargement: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        if output_path and os.path.exists(output_path):
            try:
                if os.getenv('KEEP_FILES') != 'true':
                    os.remove(output_path)
                    logger.info(f"Fichier supprimé: {output_path}")
            except Exception as e:
                logger.error(f"Erreur suppression fichier: {str(e)}")

@app.route('/health')
def health_check():
    """Point de terminaison pour vérifier l'état du service"""
    return jsonify({'status': 'ok', 'time': datetime.now().isoformat()})

if __name__ == '__main__':
    os.makedirs('downloads', exist_ok=True)
    
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
                    errorMessage.textContent = err.message || 'Une erreur s\\'est produite lors de la récupération des informations';
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
</html>''')

port = int(os.environ.get('PORT', 5000))
app.run(host='0.0.0.0', port=port)

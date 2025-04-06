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
from bs4 import BeautifulSoup
import tempfile

app = Flask(__name__)

# Configuration du logging pour Render
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler = RotatingFileHandler('/tmp/app.log', maxBytes=5000000, backupCount=3)
handler.setFormatter(formatter)
logger.addHandler(handler)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

class CustomLogger:
    def debug(self, msg):
        logger.debug(f"DEBUG: {msg}")
    
    def warning(self, msg):
        logger.warning(f"WARNING: {msg}")
    
    def error(self, msg):
        logger.error(f"ERROR: {msg}")

# Génération de User-Agent réalistes
def get_random_user_agent() -> str:
    """Génère un User-Agent réaliste et moderne"""
    # Liste de User-Agents récents et variés
    user_agents = [
        # Chrome sur Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.5615.49 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.5672.63 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.90 Safari/537.36',
        # Firefox sur Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/112.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/113.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/114.0',
        # Chrome sur Mac
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.5615.49 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.5672.63 Safari/537.36',
        # Safari sur Mac
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.3 Safari/605.1.15',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15',
        # Chrome sur Android
        'Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36',
        # Safari sur iOS
        'Mozilla/5.0 (iPhone; CPU iPhone OS 16_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Mobile/15E148 Safari/604.1'
    ]
    return random.choice(user_agents)

# Gestion des headers HTTP pour ressembler à un navigateur
def get_browser_headers() -> Dict[str, str]:
    """Génère un ensemble complet de headers HTTP réalistes"""
    # Préférences linguistiques variées
    lang_prefs = [
        "en-US,en;q=0.9",
        "en-US,en;q=0.9,fr;q=0.8",
        "en-GB,en;q=0.9,en-US;q=0.8",
        "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7"
    ]
    
    user_agent = get_random_user_agent()
    
    return {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": random.choice(lang_prefs),
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.google.com/",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "DNT": "1"
    }

# Système de rotation de proxy intelligent
class ProxyManager:
    def __init__(self):
        self.proxies = self._load_proxies()
        self.proxy_health = {proxy: {"fails": 0, "last_success": 0} for proxy in self.proxies}
        self.proxy_lock_time = 300  # secondes
        self.last_used_index = -1
        
    def _load_proxies(self) -> List[str]:
        """Charge les proxies depuis diverses sources"""
        # Essayer de charger depuis variable d'environnement
        env_proxies = os.getenv('PROXY_LIST')
        if env_proxies:
            try:
                return json.loads(env_proxies)
            except json.JSONDecodeError:
                logger.warning("Erreur de parsing du JSON des proxies")
                pass
        
        # Essayer de charger depuis un fichier
        proxy_file = 'proxies.txt'
        if os.path.exists(proxy_file):
            with open(proxy_file, 'r') as f:
                return [line.strip() for line in f if line.strip()]
        
        # Proxies par défaut (à remplacer par les vôtres)
        return [
            'http://proxy1:8080',
            'http://proxy2:8080',
            'http://proxy3:8080',
            'http://proxy4:8080',
            'http://proxy5:8080'
        ]
    
    def get_proxy(self) -> str:
        """Obtient le proxy le plus sain disponible"""
        # Si aucun proxy disponible, retourner None
        if not self.proxies:
            logger.warning("Aucun proxy disponible, tentative sans proxy")
            return None
            
        current_time = time.time()
        
        # Filtrer les proxies récemment échoués
        available_proxies = [
            p for p in self.proxies 
            if (current_time - self.proxy_health[p]["last_success"] > self.proxy_lock_time and 
                self.proxy_health[p]["fails"] >= 3) or self.proxy_health[p]["fails"] < 3
        ]
        
        if not available_proxies:
            # Tous les proxies sont verrouillés, utiliser celui avec l'échec le plus ancien
            proxy = min(self.proxies, key=lambda p: self.proxy_health[p]["last_success"])
            logger.warning(f"Tous les proxies échouent, utilisation du moins récemment échoué: {proxy}")
            return proxy
            
        # Trier par nombre d'échecs (ascendant) et dernier succès (descendant)
        proxy = sorted(
            available_proxies,
            key=lambda p: (self.proxy_health[p]["fails"], -self.proxy_health[p]["last_success"])
        )[0]
        
        logger.info(f"Proxy sélectionné: {proxy} (échecs: {self.proxy_health[proxy]['fails']})")
        return proxy
    
    def report_success(self, proxy: str):
        """Signaler une utilisation réussie du proxy"""
        if proxy and proxy in self.proxy_health:
            self.proxy_health[proxy]["fails"] = 0
            self.proxy_health[proxy]["last_success"] = time.time()
    
    def report_failure(self, proxy: str):
        """Signaler un échec d'utilisation du proxy"""
        if proxy and proxy in self.proxy_health:
            self.proxy_health[proxy]["fails"] += 1
            logger.warning(f"Proxy {proxy} compte d'échecs: {self.proxy_health[proxy]['fails']}")

proxy_manager = ProxyManager()

# Simulation de délai naturel
def natural_delay(min_seconds=2, max_seconds=5):
    """Crée un délai naturel ressemblant à un humain"""
    # Délai de base
    base_delay = random.uniform(min_seconds, max_seconds)
    
    # Petite chance d'une pause plus longue (comme si l'utilisateur était distrait)
    if random.random() < 0.05:  # 5% de chance
        base_delay += random.uniform(2, 5)
        
    # Micro-pauses pour simuler le temps de réflexion ou la latence réseau
    micro_pauses = sum(random.uniform(0.01, 0.2) for _ in range(random.randint(1, 3)))
    
    total_delay = base_delay + micro_pauses
    logger.debug(f"Pause naturelle de {total_delay:.2f} secondes")
    time.sleep(total_delay)

# Création d'une session qui imite le comportement humain
def create_human_session() -> requests.Session:
    """Crée une session avec un comportement qui ressemble à un utilisateur humain"""
    session = requests.Session()
    headers = get_browser_headers()
    session.headers.update(headers)
    
    # Définir des cookies courants
    session.cookies.set("CONSENT", f"YES+cb.{time.time():.0f}", domain=".youtube.com")
    session.cookies.set("VISITOR_INFO1_LIVE", f"{''.join(random.choices('0123456789abcdefABCDEF', k=16))}", domain=".youtube.com")
    
    return session

# Simulation de navigation humaine
def simulate_human_navigation(session: requests.Session, url: str) -> requests.Response:
    """Simule des modèles de navigation humaine avant d'accéder à l'URL cible"""
    try:
        # Chaîne de redirection: Google -> Page d'accueil YouTube -> vidéo cible
        video_id = url.split("watch?v=")[1].split("&")[0] if "watch?v=" in url else ""
        if video_id:
            google_search_url = "https://www.google.com/search?q=" + "+".join(video_id.split("-"))
            
            # Première requête vers Google
            session.get(google_search_url, timeout=10)
            natural_delay(1, 3)
            
            # Puis vers la page d'accueil YouTube
            session.get("https://www.youtube.com/", timeout=10)
            natural_delay(2, 4)
        
        # Enfin vers l'URL cible
        response = session.get(url, timeout=10)
        return response
    except Exception as e:
        logger.error(f"Erreur pendant la simulation de navigation: {e}")
        # Revenir à une requête directe
        return session.get(url, timeout=10)

def get_download_folder() -> str:
    """Crée et retourne le dossier de téléchargement approprié pour Render"""
    # Sur Render, utilisez /tmp qui est un système de fichiers temporaire
    folder = os.path.join('/tmp', 'downloads', datetime.now().strftime('%Y-%m-%d'))
    os.makedirs(folder, exist_ok=True)
    return folder

# Gestion améliorée des cookies
def manage_cookies() -> Dict:
    """Charge les cookies avec des mécanismes de secours et rotation"""
    cookies_env = os.getenv('YOUTUBE_COOKIES')
    cookies_file = os.getenv('COOKIES_FILE', 'cookies.json')
    
    cookies = {}
    
    # Essayer d'abord la variable d'environnement
    if cookies_env:
        try:
            cookies = json.loads(cookies_env)
            logger.info("Cookies chargés depuis la variable d'environnement")
        except json.JSONDecodeError:
            logger.warning("Échec de l'analyse des cookies depuis la variable d'environnement")
    
    # Ensuite essayer le fichier
    if not cookies and os.path.exists(cookies_file):
        try:
            with open(cookies_file, 'r') as f:
                cookies = json.load(f)
                logger.info(f"Cookies chargés depuis {cookies_file}")
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Échec du chargement des cookies depuis le fichier: {e}")
    
    # Ajouter des cookies YouTube courants si nous n'en avons pas
    if not cookies:
        logger.info("Pas de cookies trouvés, génération de cookies de secours")
        cookies = {
            "CONSENT": f"YES+cb.{time.time():.0f}",
            "VISITOR_INFO1_LIVE": ''.join(random.choices('0123456789abcdefABCDEF', k=16)),  
            "YSC": ''.join(random.choices('0123456789abcdefABCDEF', k=11)),
            "GPS": "1",
            "PREF": f"f4={random.randint(10000, 99999)}&f5={random.randint(10000, 99999)}"
        }
    
    return cookies

def save_cookies_to_file(cookies: Dict):
    """Sauvegarde les cookies dans l'environnement et le fichier"""
    try:
        # Sauvegarder dans l'environnement
        os.environ['YOUTUBE_COOKIES'] = json.dumps(cookies)
        
        # Sauvegarder dans le fichier
        cookies_file = os.getenv('COOKIES_FILE', '/tmp/cookies.json')
        with open(cookies_file, 'w') as f:
            json.dump(cookies, f)
            
        logger.info("Cookies sauvegardés avec succès")
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde des cookies: {e}")

# Détection de Captcha
def detect_captcha(html_content: str) -> bool:
    """Détecte si une réponse contient un défi captcha"""
    captcha_indicators = [
        'www.google.com/recaptcha',
        'g-recaptcha',
        'captcha',
        'solving the above captcha',
        'security check',
        'Confirm you are not a robot',  # Corrigé: apostrophe échappée
        'challenge-form',
        'challenge-running',
        'unusual traffic'
    ]
    
    for indicator in captcha_indicators:
        if indicator in html_content.lower():
            logger.warning(f"Captcha détecté: trouvé '{indicator}'")
            return True
    
    return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/info', methods=['POST'])
def video_info():
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'No URL provided'}), 400

        url = data['url']
        logger.info(f"Extraction des infos pour: {url}")
        
        # Créer un fichier temporaire pour les cookies
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as temp_cookies:
            temp_cookies_path = temp_cookies.name
            
            # Première approche: Essayer avec une session ressemblant à un humain
            try:
                session = create_human_session()
                proxy = proxy_manager.get_proxy()
                if proxy:
                    session.proxies = {"http": proxy, "https": proxy}
                
                # Simuler une navigation naturelle
                natural_delay(1, 3)
                response = simulate_human_navigation(session, url)
                
                if detect_captcha(response.text):
                    logger.warning("Captcha détecté dans la navigation initiale")
                    # Passer à une approche différente en cas de captcha
                    raise Exception("Captcha détecté")
                
                # Sauvegarder les cookies de la session dans le fichier
                cookies_dict = {name: value for name, value in session.cookies.items()}
                
                # Sauvegarder les cookies dans le fichier temporaire au format Netscape
                with open(temp_cookies_path, 'w') as f:
                    f.write("# Netscape HTTP Cookie File\n")
                    for domain, cookies in session.cookies._cookies.items():
                        for path, cookies_by_path in cookies.items():
                            for name, cookie in cookies_by_path.items():
                                f.write(f"{cookie.domain}\tTRUE\t{cookie.path}\t"
                                      f"{'TRUE' if cookie.secure else 'FALSE'}\t"
                                      f"{cookie.expires if cookie.expires else 0}\t"
                                      f"{cookie.name}\t{cookie.value}\n")
                
                if proxy:
                    proxy_manager.report_success(proxy)
            except Exception as e:
                logger.warning(f"Approche de session humaine échouée: {e}")
                # Continuer vers la méthode de secours
            
            # Préparer les options yt-dlp avec des paramètres anti-détection avancés
            headers = get_browser_headers()
            proxy = proxy_manager.get_proxy()
            
            ydl_opts = {
                'quiet': True,
                'skip_download': True,
                'no_call_home': True,
                'geo_bypass': True,
                'geo_bypass_country': 'US',
                'prefer_free_formats': True,
                'nocheckcertificate': True,
                'socket_timeout': 15,
                'extractor_retries': 5,
                'fragmentretries': 5,
                'user_agent': headers["User-Agent"],
                'http_headers': headers,
                'proxy': proxy,
                'cookiefile': temp_cookies_path,
                'logger': CustomLogger(),
                'sleep_interval_requests': random.randint(2, 5),
                'sleep_interval': random.randint(1, 3),
                'sleep_interval_subtitles': random.randint(1, 3)
            }
            
            natural_delay(1.5, 3.5)
            
            formats = []
            title = ''
            thumbnail = ''
            duration = 0
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    
                    if isinstance(info, str) and detect_captcha(info):
                        logger.warning("Captcha détecté dans la réponse yt-dlp")
                        if proxy:
                            proxy_manager.report_failure(proxy)
                        return jsonify({'error': 'Captcha détecté, veuillez réessayer dans quelques minutes'}), 429
                    
                    title = info.get('title', '')
                    thumbnail = info.get('thumbnail', '')
                    duration = info.get('duration', 0)
                    
                    formats = [{
                        'format_id': f.get('format_id', ''),
                        'ext': f.get('ext', ''),
                        'resolution': f.get('resolution') or f"{f.get('height', '')}p",
                        'format_note': f.get('format_note', ''),
                        'filesize': f.get('filesize') or f.get('filesize_approx') or 0
                    } for f in info.get('formats', []) if 
                      (f.get('vcodec') != 'none' or f.get('acodec') != 'none') and
                      (f.get('format_id') not in ['source']) and 
                      (f.get('ext') in ['mp4', 'webm', 'm4a', 'mp3', 'ogg'])]
                    
                    # Garder seulement un nombre raisonnable de formats pour éviter les soupçons
                    if len(formats) > 8:
                        # Sélectionner une bonne variété tout en limitant les options
                        resolutions = {}
                        for f in formats:
                            res = f.get('resolution', '')
                            if res not in resolutions or f.get('filesize', 0) > resolutions[res].get('filesize', 0):
                                resolutions[res] = f
                        
                        formats = list(resolutions.values())
                    
                    if proxy:
                        proxy_manager.report_success(proxy)
                    natural_delay(0.5, 2)
                    
                    logger.info("Extraction réussie")
            except Exception as e:
                logger.error(f"Erreur pendant l'extraction yt-dlp: {e}")
                if proxy:
                    proxy_manager.report_failure(proxy)
                return jsonify({'error': str(e)}), 500
            finally:
                # Nettoyer le fichier temporaire
                try:
                    os.unlink(temp_cookies_path)
                except Exception:
                    pass
            
            return jsonify({
                'success': True,
                'title': title,
                'thumbnail': thumbnail,
                'duration': duration,
                'formats': formats
            })
    except Exception as e:
        logger.error(f"Erreur générale dans l'endpoint info: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/download', methods=['POST'])
def download_video():
    output_path = None
    temp_cookies_path = None
    
    try:
        data = request.get_json()
        if not data or 'url' not in data or 'format_id' not in data:
            return jsonify({'error': 'URL ou format_id manquant'}), 400

        url = data['url']
        format_id = data['format_id']
        logger.info(f"Téléchargement de la vidéo: {url} au format {format_id}")

        # Créer un nom de fichier unique
        filename = f"video_{uuid.uuid4().hex}.mp4"
        output_path = os.path.join(get_download_folder(), filename)
        
        # Créer un fichier temporaire pour les cookies
        temp_fd, temp_cookies_path = tempfile.mkstemp(suffix='.txt')
        os.close(temp_fd)
        
        # Créer une session ressemblant à un humain pour préparer la connexion
        session = create_human_session()
        proxy = proxy_manager.get_proxy()
        if proxy:
            session.proxies = {"http": proxy, "https": proxy}
        
        # Simuler une navigation naturelle avant le téléchargement
        try:
            natural_delay(1, 3)
            response = simulate_human_navigation(session, url)
            
            if detect_captcha(response.text):
                logger.warning("Captcha détecté dans la navigation pré-téléchargement")
                if proxy:
                    proxy_manager.report_failure(proxy)
                # Nous essaierons une approche différente ci-dessous
            else:
                # Sauvegarder les cookies de la session dans le fichier
                cookies_dict = {name: value for name, value in session.cookies.items()}
                
                # Sauvegarder les cookies au format Netscape
                with open(temp_cookies_path, 'w') as f:
                    f.write("# Netscape HTTP Cookie File\n")
                    for domain, cookies in session.cookies._cookies.items():
                        for path, cookies_by_path in cookies.items():
                            for name, cookie in cookies_by_path.items():
                                f.write(f"{cookie.domain}\tTRUE\t{cookie.path}\t"
                                      f"{'TRUE' if cookie.secure else 'FALSE'}\t"
                                      f"{cookie.expires if cookie.expires else 0}\t"
                                      f"{cookie.name}\t{cookie.value}\n")
        except Exception as e:
            logger.warning(f"Navigation pré-téléchargement échouée: {e}")
            # Retour aux cookies par défaut
            cookies = manage_cookies()
            with open(temp_cookies_path, 'w') as f:
                for domain, name, value in [('.youtube.com', k, v) for k, v in cookies.items()]:
                    f.write(f"{domain}\tTRUE\t/\tFALSE\t{int(time.time() + 3600*24*365)}\t{name}\t{value}\n")
        
        # Configuration des options yt-dlp avancées pour imiter le comportement humain
        headers = get_browser_headers()
        proxy = proxy_manager.get_proxy()  # Obtenir un proxy potentiellement différent pour le téléchargement
        
        natural_delay(2, 5)
        
        ydl_opts = {
            'format': format_id,
            'outtmpl': output_path,
            'no_call_home': True,
            'geo_bypass': True,
            'geo_bypass_country': 'US',
            'prefer_free_formats': True,
            'nocheckcertificate': True,
            'socket_timeout': 30,
            'extractor_retries': 5,
            'fragmentretries': 10,
            'retries': 10,
            'user_agent': headers["User-Agent"],
            'http_headers': headers,
            'proxy': proxy,
            'cookiefile': temp_cookies_path,
            'logger': CustomLogger(),
            'restrictfilenames': True,
            'merge_output_format': 'mp4',
            'write_description': False,  # Ne pas attirer l'attention avec des requêtes supplémentaires
            'write_info_json': False,
            'write_thumbnail': False,
            'sleep_interval_requests': random.randint(3, 6),
            'sleep_interval': random.randint(1, 3),
            'sleep_interval_subtitles': random.randint(1, 3)
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            natural_delay(3, 7)
            ydl.download([url])
            logger.info(f"Téléchargement terminé: {output_path}")
            if proxy:
                proxy_manager.report_success(proxy)
            
            return send_file(output_path, as_attachment=True)
    except Exception as e:
        logger.error(f"Erreur pendant le téléchargement: {e}")
        if 'proxy' in locals() and proxy:
            proxy_manager.report_failure(proxy)
        return jsonify({'error': str(e)}), 500
    finally:
        # Nettoyer les fichiers
        if output_path and os.path.exists(output_path):
            try:
                os.remove(output_path)
                logger.info(f"Fichier supprimé: {output_path}")
            except Exception as remove_error:
                logger.error(f"Erreur lors de la suppression du fichier {output_path}: {remove_error}")
        
        if temp_cookies_path and os.path.exists(temp_cookies_path):
            try:
                os.remove(temp_cookies_path)
            except Exception:
                pass

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint de vérification d'état de base qui valide également la connectivité YouTube"""
    try:
        # Créer une session et tester l'accès à YouTube
        session = create_human_session()
        proxy = proxy_manager.get_proxy()
        if proxy:
            session.proxies = {"http": proxy, "https": proxy}
        
        response = session.get("https://www.youtube.com/", timeout=10)
        if response.status_code == 200 and not detect_captcha(response.text):
            if proxy:
                proxy_manager.report_success(proxy)
            return jsonify({"status": "ok", "youtube_access": True})
        else:
            if proxy:
                proxy_manager.report_failure(proxy)
            return jsonify({"status": "degraded", "youtube_access": False}), 503
    except Exception as e:
        logger.error(f"Échec de la vérification de l'état: {e}")
        if 'proxy' in locals() and proxy:
            proxy_manager.report_failure(proxy)
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # Utiliser dossiers temporaires pour Render
    os.makedirs('/tmp/downloads', exist_ok=True)
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

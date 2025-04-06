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
import re
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import tempfile

app = Flask(__name__)

# Advanced logging configuration
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler = RotatingFileHandler('app.log', maxBytes=5000000, backupCount=3)
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

# Realistic browser fingerprinting
def generate_realistic_browser_fingerprint() -> Dict:
    """Generate a comprehensive and realistic browser fingerprint"""
    # Modern browser configurations
    browsers = [
        {
            "name": "Chrome",
            "versions": ["111.0.5563.64", "112.0.5615.49", "113.0.5672.63", "114.0.5735.90"],
            "platforms": [
                "Windows NT 10.0; Win64; x64",
                "Windows NT 11.0; Win64; x64",
                "Macintosh; Intel Mac OS X 10_15_7",
                "Macintosh; Intel Mac OS X 11_6_0",
                "X11; Linux x86_64"
            ]
        },
        {
            "name": "Firefox",
            "versions": ["111.0", "112.0", "113.0.1", "114.0"],
            "platforms": [
                "Windows NT 10.0; Win64; x64",
                "Windows NT 11.0; Win64; x64", 
                "Macintosh; Intel Mac OS X 10.15",
                "Macintosh; Intel Mac OS X 11.6",
                "X11; Linux x86_64"
            ]
        },
        {
            "name": "Safari",
            "versions": ["15.4", "15.5", "16.0", "16.1"],
            "platforms": [
                "Macintosh; Intel Mac OS X 10_15_7",
                "Macintosh; Intel Mac OS X 11_6_0"
            ]
        }
    ]
    
    browser = random.choice(browsers)
    version = random.choice(browser["versions"])
    platform = random.choice(browser["platforms"])
    
    if browser["name"] == "Chrome":
        user_agent = f"Mozilla/5.0 ({platform}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version} Safari/537.36"
    elif browser["name"] == "Firefox":
        user_agent = f"Mozilla/5.0 ({platform}; rv:{version}) Gecko/20100101 Firefox/{version}"
    else:  # Safari
        user_agent = f"Mozilla/5.0 ({platform}) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/{version} Safari/605.1.15"
    
    # Common language preferences
    lang_prefs = [
        "en-US,en;q=0.9",
        "en-US,en;q=0.9,fr;q=0.8",
        "en-GB,en;q=0.9,en-US;q=0.8",
        "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7"
    ]
    
    # Create a set of request headers that mimics a real browser
    return {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": random.choice(lang_prefs),
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.google.com/",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
        "Sec-Ch-Ua": f'"{browser["name"]}";v="{version.split(".")[0]}", "Not=A?Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": f'"{platform.split(";")[0].replace("Windows NT", "Windows").replace("Macintosh; Intel Mac OS X", "macOS")}"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "DNT": "1"
    }

# Intelligent proxy rotation with retry and health check
class ProxyManager:
    def __init__(self):
        self.proxies = self._load_proxies()
        self.proxy_health = {proxy: {"fails": 0, "last_success": 0} for proxy in self.proxies}
        self.proxy_lock_time = 300  # seconds to lock out a failing proxy
        
    def _load_proxies(self) -> List[str]:
        # Try to load from env var or file, fallback to defaults
        env_proxies = os.getenv('PROXY_LIST')
        if env_proxies:
            try:
                return json.loads(env_proxies)
            except:
                pass
        
        proxy_file = 'proxies.txt'
        if os.path.exists(proxy_file):
            with open(proxy_file, 'r') as f:
                return [line.strip() for line in f if line.strip()]
        
        # Default proxies
        return [
            'http://proxy1:8080',
            'http://proxy2:8080',
            'http://proxy3:8080',
            'http://proxy4:8080',
            'http://proxy5:8080',
            'http://proxy6:8080',
            'http://proxy7:8080',
            'http://proxy8:8080'
        ]
    
    def get_proxy(self) -> str:
        """Get the healthiest available proxy"""
        current_time = time.time()
        
        # Filter out recently failed proxies
        available_proxies = [
            p for p in self.proxies 
            if (current_time - self.proxy_health[p]["last_success"] > self.proxy_lock_time and 
                self.proxy_health[p]["fails"] >= 3) or self.proxy_health[p]["fails"] < 3
        ]
        
        if not available_proxies:
            # All proxies are locked, use the one with the oldest failure
            proxy = min(self.proxies, key=lambda p: self.proxy_health[p]["last_success"])
            logger.warning(f"All proxies are failing, using least recently failed: {proxy}")
            return proxy
            
        # Sort by failure count (ascending) and last success time (descending)
        proxy = sorted(
            available_proxies,
            key=lambda p: (self.proxy_health[p]["fails"], -self.proxy_health[p]["last_success"])
        )[0]
        
        logger.info(f"Selected proxy: {proxy} (fails: {self.proxy_health[proxy]['fails']})")
        return proxy
    
    def report_success(self, proxy: str):
        """Report a successful use of proxy"""
        self.proxy_health[proxy]["fails"] = 0
        self.proxy_health[proxy]["last_success"] = time.time()
    
    def report_failure(self, proxy: str):
        """Report a failed use of proxy"""
        self.proxy_health[proxy]["fails"] += 1
        logger.warning(f"Proxy {proxy} failure count: {self.proxy_health[proxy]['fails']}")

proxy_manager = ProxyManager()

# Create a session that mimics human behavior
def create_human_session() -> requests.Session:
    """Create a session with behavior that resembles a human user"""
    session = requests.Session()
    headers = generate_realistic_browser_fingerprint()
    session.headers.update(headers)
    
    # Set common cookies (can be customized)
    session.cookies.set("CONSENT", f"YES+cb.{time.time():.0f}", domain=".youtube.com")
    session.cookies.set("VISITOR_INFO1_LIVE", f"{''.join(random.choices('0123456789abcdefABCDEF', k=16))}", domain=".youtube.com")
    
    return session

# Human-like navigational patterns
def simulate_human_navigation(session: requests.Session, url: str) -> requests.Response:
    """Simulate human-like navigation patterns before accessing the target URL"""
    try:
        # Redirect chain: Google -> YouTube homepage -> target video
        google_search_url = "https://www.google.com/search?q=" + "+".join(url.split("watch?v=")[1].split("&")[0].split("-"))
        
        # First request to Google
        session.get(google_search_url, timeout=10)
        natural_delay(2, 4)
        
        # Then to YouTube homepage
        session.get("https://www.youtube.com/", timeout=10)
        natural_delay(3, 6)
        
        # Finally to the target URL
        response = session.get(url, timeout=10)
        return response
    except Exception as e:
        logger.error(f"Error during navigation simulation: {e}")
        # Fallback to direct request
        return session.get(url, timeout=10)

# More sophisticated randomized delay function
def natural_delay(min_seconds=2, max_seconds=5):
    """Create a natural human-like delay with some randomness"""
    # Base delay
    base_delay = random.uniform(min_seconds, max_seconds)
    
    # Add small chance of longer pause (as if user got distracted)
    if random.random() < 0.05:  # 5% chance
        base_delay += random.uniform(2, 8)
        
    # Add tiny micro-pauses to simulate think time or network jitter
    micro_pauses = sum(random.uniform(0.01, 0.2) for _ in range(random.randint(1, 3)))
    
    total_delay = base_delay + micro_pauses
    logger.debug(f"Natural pause of {total_delay:.2f} seconds")
    time.sleep(total_delay)

def get_download_folder() -> str:
    folder = os.path.join('downloads', datetime.now().strftime('%Y-%m-%d'))
    os.makedirs(folder, exist_ok=True)
    return folder

# Enhanced cookie management
def manage_cookies() -> Dict:
    """Load cookies with fallback mechanisms and rotation"""
    cookies_env = os.getenv('YOUTUBE_COOKIES')
    cookies_file = os.getenv('COOKIES_FILE', 'cookies.json')
    
    cookies = {}
    
    # Try environment variable first
    if cookies_env:
        try:
            cookies = json.loads(cookies_env)
            logger.info("Loaded cookies from environment variable")
        except json.JSONDecodeError:
            logger.warning("Failed to parse cookies from environment variable")
    
    # Then try file
    if not cookies and os.path.exists(cookies_file):
        try:
            with open(cookies_file, 'r') as f:
                cookies = json.load(f)
                logger.info(f"Loaded cookies from {cookies_file}")
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load cookies from file: {e}")
    
    # Add some common YouTube cookies if we don't have any
    if not cookies:
        logger.info("No cookies found, generating fallback cookies")
        cookies = {
            "CONSENT": f"YES+cb.{time.time():.0f}",
            "VISITOR_INFO1_LIVE": ''.join(random.choices('0123456789abcdefABCDEF', k=16)),  
            "YSC": ''.join(random.choices('0123456789abcdefABCDEF', k=11)),
            "GPS": "1",
            "PREF": f"f4={random.randint(10000, 99999)}&f5={random.randint(10000, 99999)}"
        }
    
    return cookies

def save_cookies_to_file(cookies: Dict):
    """Save cookies to both environment and file"""
    try:
        # Save to environment
        os.environ['YOUTUBE_COOKIES'] = json.dumps(cookies)
        
        # Save to file
        cookies_file = os.getenv('COOKIES_FILE', 'cookies.json')
        with open(cookies_file, 'w') as f:
            json.dump(cookies, f)
            
        logger.info("Successfully saved cookies")
    except Exception as e:
        logger.error(f"Error saving cookies: {e}")

# Captcha detection and handling
def detect_captcha(html_content: str) -> bool:
    """Detect if a response contains a captcha challenge"""
    captcha_indicators = [
        'www.google.com/recaptcha',
        'g-recaptcha',
        'captcha',
        'solving the above captcha',
        'security check',
        'Confirm you're not a robot',
        'challenge-form',
        'challenge-running',
        'unusual traffic'
    ]
    
    for indicator in captcha_indicators:
        if indicator in html_content.lower():
            logger.warning(f"Captcha detected: found '{indicator}'")
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
        logger.info(f"Extracting info for: {url}")
        
        # Create temp file for cookies
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as temp_cookies:
            temp_cookies_path = temp_cookies.name
            
            # First approach: Try with human-like session
            try:
                session = create_human_session()
                proxy = proxy_manager.get_proxy()
                session.proxies = {"http": proxy, "https": proxy}
                
                # Simulate natural browsing
                natural_delay(1, 3)
                response = simulate_human_navigation(session, url)
                
                if detect_captcha(response.text):
                    logger.warning("Captcha detected in initial navigation")
                    # Switch to a different approach on captcha
                    raise Exception("Captcha detected")
                
                # Save cookies from the session to file
                cookies_dict = {name: value for name, value in session.cookies.items()}
                
                # Save cookies to the temp file in Netscape format
                with open(temp_cookies_path, 'w') as f:
                    f.write("# Netscape HTTP Cookie File\n")
                    for domain, cookies in session.cookies._cookies.items():
                        for path, cookies_by_path in cookies.items():
                            for name, cookie in cookies_by_path.items():
                                f.write(f"{cookie.domain}\tTRUE\t{cookie.path}\t"
                                      f"{'TRUE' if cookie.secure else 'FALSE'}\t"
                                      f"{cookie.expires if cookie.expires else 0}\t"
                                      f"{cookie.name}\t{cookie.value}\n")
                
                proxy_manager.report_success(proxy)
            except Exception as e:
                logger.warning(f"Human-like session approach failed: {e}")
                # Continue to fallback method
            
            # Prepare yt-dlp options with advanced anti-detection settings
            headers = generate_realistic_browser_fingerprint()
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
                        logger.warning("Captcha detected in yt-dlp response")
                        proxy_manager.report_failure(proxy)
                        return jsonify({'error': 'Captcha detected, please try again in a few minutes'}), 429
                    
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
                    
                    # Keep only a reasonable number of formats to avoid suspicion
                    if len(formats) > 8:
                        # Select a good variety while limiting options
                        resolutions = {}
                        for f in formats:
                            res = f.get('resolution', '')
                            if res not in resolutions or f.get('filesize', 0) > resolutions[res].get('filesize', 0):
                                resolutions[res] = f
                        
                        formats = list(resolutions.values())
                    
                    proxy_manager.report_success(proxy)
                    natural_delay(0.5, 2)
                    
                    logger.info("Extraction successful")
            except Exception as e:
                logger.error(f"Error during yt-dlp extraction: {e}")
                proxy_manager.report_failure(proxy)
                return jsonify({'error': str(e)}), 500
            finally:
                # Clean up temp file
                try:
                    os.unlink(temp_cookies_path)
                except:
                    pass
            
            return jsonify({
                'success': True,
                'title': title,
                'thumbnail': thumbnail,
                'duration': duration,
                'formats': formats
            })
    except Exception as e:
        logger.error(f"General error in info endpoint: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/download', methods=['POST'])
def download_video():
    output_path = None
    temp_cookies_path = None
    
    try:
        data = request.get_json()
        if not data or 'url' not in data or 'format_id' not in data:
            return jsonify({'error': 'Missing URL or format_id'}), 400

        url = data['url']
        format_id = data['format_id']
        logger.info(f"Downloading video: {url} in format {format_id}")

        # Create unique filename
        filename = f"video_{uuid.uuid4().hex}.mp4"
        output_path = os.path.join(get_download_folder(), filename)
        
        # Create temp file for cookies
        temp_fd, temp_cookies_path = tempfile.mkstemp(suffix='.txt')
        os.close(temp_fd)
        
        # Create a human-like session to warm up the connection
        session = create_human_session()
        proxy = proxy_manager.get_proxy()
        session.proxies = {"http": proxy, "https": proxy}
        
        # Simulate natural browsing before download
        try:
            natural_delay(1, 3)
            response = simulate_human_navigation(session, url)
            
            if detect_captcha(response.text):
                logger.warning("Captcha detected in pre-download navigation")
                proxy_manager.report_failure(proxy)
                # We'll try a different approach below
            else:
                # Save cookies from the session to file
                cookies_dict = {name: value for name, value in session.cookies.items()}
                
                # Save cookies in Netscape format
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
            logger.warning(f"Pre-download navigation failed: {e}")
            # Fall back to default cookies
            cookies = manage_cookies()
            with open(temp_cookies_path, 'w') as f:
                for domain, name, value in [('.youtube.com', k, v) for k, v in cookies.items()]:
                    f.write(f"{domain}\tTRUE\t/\tFALSE\t{int(time.time() + 3600*24*365)}\t{name}\t{value}\n")
        
        # Setup advanced yt-dlp options to mimic human behavior
        headers = generate_realistic_browser_fingerprint()
        proxy = proxy_manager.get_proxy()  # Get a potentially different proxy for download
        
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
            'write_description': False,  # Don't attract attention with extra requests
            'write_info_json': False,
            'write_thumbnail': False,
            'sleep_interval_requests': random.randint(3, 6),
            'sleep_interval': random.randint(1, 3),
            'sleep_interval_subtitles': random.randint(1, 3),
            'external_downloader': 'aria2c' if os.system('which aria2c >/dev/null 2>&1') == 0 else None,
            'external_downloader_args': ['-x', '8', '-s', '8', '-k', '1M', '--retry-wait=3'] if os.system('which aria2c >/dev/null 2>&1') == 0 else None
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            natural_delay(3, 7)
            ydl.download([url])
            logger.info(f"Download completed: {output_path}")
            proxy_manager.report_success(proxy)
            
            return send_file(output_path, as_attachment=True)
    except Exception as e:
        logger.error(f"Error during download: {e}")
        if proxy:
            proxy_manager.report_failure(proxy)
        return jsonify({'error': str(e)}), 500
    finally:
        # Clean up files
        if output_path and os.path.exists(output_path):
            try:
                os.remove(output_path)
                logger.info(f"File deleted: {output_path}")
            except Exception as remove_error:
                logger.error(f"Error deleting file {output_path}: {remove_error}")
        
        if temp_cookies_path and os.path.exists(temp_cookies_path):
            try:
                os.remove(temp_cookies_path)
            except:
                pass

@app.route('/health', methods=['GET'])
def health_check():
    """Basic health check endpoint that also validates YouTube connectivity"""
    try:
        # Create a session and test access to YouTube
        session = create_human_session()
        proxy = proxy_manager.get_proxy()
        session.proxies = {"http": proxy, "https": proxy}
        
        response = session.get("https://www.youtube.com/", timeout=10)
        if response.status_code == 200 and not detect_captcha(response.text):
            proxy_manager.report_success(proxy)
            return jsonify({"status": "ok", "youtube_access": True})
        else:
            proxy_manager.report_failure(proxy)
            return jsonify({"status": "degraded", "youtube_access": False}), 503
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        if 'proxy' in locals():
            proxy_manager.report_failure(proxy)
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    os.makedirs('downloads', exist_ok=True)
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))

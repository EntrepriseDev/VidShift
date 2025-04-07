# gunicorn.conf.py
import os
import random
import multiprocessing

# Nombre de workers calculé en fonction des CPU disponibles
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'gevent'  # Utilise gevent pour de meilleures performances

# Timeouts plus longs pour gérer les téléchargements de vidéos
timeout = 300  # 5 minutes
keepalive = 5

# Ecouter sur le port attribué par Render
bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"

# Configuration de logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Paramètres avancés pour améliorer les performances
max_requests = 1000
max_requests_jitter = 50  # Jitter pour éviter que tous les workers ne redémarrent en même temps
worker_connections = 1000

# Précharger l'application pour des démarrages plus rapides
preload_app = True

# Paramètres supplémentaires pour éviter la détection de bot
def post_fork(server, worker):
    # Utiliser un délai de démarrage aléatoire pour chaque worker
    worker.timeout = timeout + random.randint(-30, 30)

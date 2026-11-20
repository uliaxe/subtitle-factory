# Manuel d'installation

Ce manuel s'adresse à l'administrateur de la solution. Il permet d'**installer**, **arrêter**
et **relancer** la solution de sous-titrage avec Docker, sur un poste ou un serveur équipé
d'une carte NVIDIA. Une variante sans carte graphique existe (section 6).

La solution comprend trois conteneurs, décrits dans `docker-compose.yml` :

| Conteneur | Rôle | Accessible depuis l'extérieur |
|---|---|---|
| `app` | Interface web et API (FastAPI) | Oui, port 8000 (réglable) |
| `db` | Base de données PostgreSQL : comptes, historique | Non |
| `ai` | Service IA : Whisper sur carte graphique, ffmpeg | Non |

Les données sont conservées dans des volumes Docker : elles survivent aux arrêts,
redémarrages et mises à jour.

## 1. Prérequis

| Élément | Serveur Linux (production) | Poste Windows (démo) |
|---|---|---|
| Carte graphique | NVIDIA, 4 Go de mémoire minimum (24 Go pour 10 utilisateurs, ex. L4) | Idem |
| Pilote NVIDIA | Récent (CUDA 12.4 ou plus) | Pilote Windows récent ; il est partagé avec Docker |
| Docker | Docker Engine + plugin Compose | Docker Desktop (moteur WSL 2) |
| Accès GPU pour Docker | NVIDIA Container Toolkit | Inclus dans Docker Desktop |
| Disque | ~15 Go (images, modèle) + la place des vidéos | Idem |

Vérifier que Docker voit la carte graphique :

```bash
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

La commande doit afficher le nom de la carte. Sinon, revoir le pilote et le NVIDIA Container Toolkit.

## 2. Installation

```bash
git clone https://github.com/uliaxe/subtitle-factory.git
cd "subtitle-factory/projet fil rouge"
cp .env.example .env
```

Ouvrir `.env` et **changer** au minimum `POSTGRES_PASSWORD` et `ADMIN_PASSWORD`.
Adapter `NUM_WORKERS` à la carte : 1 pour 4 Go (meilleur débit mesuré), 10 pour une L4 (24 Go).

Construire et démarrer :

```bash
docker compose up -d --build
```

Le premier démarrage prend plusieurs minutes : construction des images, puis téléchargement
du modèle Whisper (~1,5 Go) par le service IA. Suivre l'avancement :

```bash
docker compose logs -f ai
```

Le service est prêt quand le journal affiche « N workers prêts ». L'interface est alors
disponible sur **http://localhost:8000** (ou l'adresse du serveur). Se connecter avec le compte
admin du fichier `.env`.

## 3. Vérifier que tout fonctionne

```bash
docker compose ps
```

Les trois services doivent être `running` et `healthy`. L'application répond aussi sur
`http://localhost:8000/healthz`.

## 4. Arrêter, relancer, mettre à jour

| Action | Commande |
|---|---|
| Arrêter la solution | `docker compose stop` |
| Relancer après un arrêt | `docker compose start` |
| Redémarrer | `docker compose restart` |
| Mettre à jour après un `git pull` | `docker compose up -d --build` |
| Voir les journaux | `docker compose logs -f` (ou `logs -f app`, `logs -f ai`) |
| Tout supprimer, **données comprises** | `docker compose down -v` (irréversible) |

**Après un crash** : chaque conteneur a la règle `restart: unless-stopped`. Docker le relance
tout seul s'il s'arrête, et au redémarrage de la machine (si Docker démarre avec elle).
Les traitements qui étaient en cours sont marqués « échoués » au redémarrage, avec leur cause,
et restent visibles dans les statistiques. Si un worker IA plante, le service le recrée seul.

## 5. Réglages (`.env`)

| Variable | Défaut | Effet |
|---|---|---|
| `POSTGRES_PASSWORD` | à définir | Mot de passe interne de la base |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | `admin` / à définir | Compte admin créé au premier démarrage |
| `APP_PORT` | `8000` | Port de l'interface sur la machine |
| `NUM_WORKERS` | `1` | Traitements simultanés ; au-delà, refus immédiat (pas de file d'attente) |
| `WHISPER_MODEL` | `medium.en` | Modèle de transcription |
| `WHISPER_COMPUTE_TYPE` | `int8_float16` | Compression du modèle (~1 Go de mémoire GPU par worker) |
| `WHISPER_BEAM_SIZE` | `5` | Largeur de recherche ; avec le mode par lots, garder 5 (1 fait sauter des passages) |
| `WHISPER_BATCH_SIZE` | `8` | Mode par lots de faster-whisper (0 = désactivé) ; +50 % de débit mesuré |
| `RETENTION_DAYS` | `7` | Durée de conservation des fichiers utilisateur |

Après une modification : `docker compose up -d`.

## 6. Machine sans carte NVIDIA

La transcription tourne alors sur le processeur, avec un modèle plus petit et un seul
traitement à la fois. C'est plus lent que la durée de la vidéo : à réserver aux essais.

```bash
docker compose -f docker-compose.yml -f docker-compose.cpu.yml up -d --build
```

## 7. Déploiement sur un serveur cloud (procédure prévue)

Procédure prévue pour une instance Scaleway L4-1-24G (Ubuntu, GPU NVIDIA L4 24 Go),
non testée faute de location :

1. Créer l'instance avec l'image Ubuntu « GPU OS » de Scaleway, qui inclut le pilote NVIDIA,
   Docker et le NVIDIA Container Toolkit.
2. Ouvrir uniquement le port de l'application (ou 443 derrière un reverse proxy HTTPS).
3. Suivre les sections 2 à 4, avec `NUM_WORKERS=10` dans `.env`.

## 8. Dépannage

| Problème | Solution |
|---|---|
| `could not select device driver "nvidia"` | Docker ne voit pas la carte : installer le NVIDIA Container Toolkit (Linux) ou mettre à jour Docker Desktop et le pilote (Windows) |
| `port is already allocated` | Changer `APP_PORT` dans `.env` |
| `ADMIN_PASSWORD … à définir dans .env` | Le fichier `.env` manque : `cp .env.example .env` |
| L'interface ne répond pas après `up` | Normal au premier lancement : attendre « workers prêts » dans `docker compose logs -f ai` |
| Traitement « Service IA saturé » | Tous les workers sont pris : réessayer, ou augmenter `NUM_WORKERS` si la carte a la mémoire |
| Erreur de mémoire GPU (`out of memory`) | Baisser `NUM_WORKERS` |

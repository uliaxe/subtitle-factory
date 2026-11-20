# Sous-titrage : application web

API applicative, base de données et interface web du projet fil rouge.
Elle ne contient pas d'IA : la transcription est déléguée à un service IA séparé
sur le serveur GPU (validé avec le conseiller technique), appelé en HTTP avec
`AI_BACKEND=http`. Une IA simulée (`AI_BACKEND=fake`) permet de tout faire tourner sans GPU.

Pour un déploiement complet (application, PostgreSQL, service IA), voir `../INSTALL.md`.

## Installation

Prérequis : Python 3.11 ou plus récent. ffmpeg est facultatif (il sert à mesurer la durée des médias).

```bash
cd subtitle_app
pip install -r requirements.txt
cp .env.example .env        # puis changer ADMIN_PASSWORD
```

## Lancer, arrêter, relancer

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Sous Windows, `python -m uvicorn` évite le blocage de `uvicorn.exe` par le contrôle d'application.

- Interface : http://localhost:8000. Le compte admin est celui du fichier `.env`.
- Documentation de l'API (Swagger) : http://localhost:8000/docs
- Supervision : `GET /healthz`
- Arrêt : `Ctrl+C`. Relance : la même commande.

Après un crash, les traitements qui étaient en cours sont marqués « échoués » au redémarrage.
Ils restent donc visibles dans les statistiques.

## Tests

```bash
python -m pytest
```

## Fonctionnement

| Exigence | Réalisation |
|---|---|
| Upload .mp4 / .wav, choix du résultat | `POST /api/v1/jobs`. Les combinaisons interdites (audio vers vidéo) sont refusées |
| Pas de file d'attente, 10 en parallèle | Au-delà de `MAX_CONCURRENT_JOBS`, refus immédiat (HTTP 429) |
| Consulter et télécharger le résultat | Bouton « Voir » (texte, .srt, vidéo) et « Télécharger » |
| Fichiers utilisateur : 7 jours max | Purge automatique toutes les heures, et bouton « Supprimer » |
| Historique admin permanent | Les lignes `jobs` ne sont jamais supprimées, le texte compris |
| Statistiques admin | `GET /api/v1/admin/stats` : temps moyen, inférences, non terminés et échecs, par type |
| Rôles utilisateur / admin | Jeton Bearer, routes `/admin/*` réservées aux admins |
| Inscription | Libre via « Créer un compte » (`POST /api/v1/auth/register`), toujours en rôle utilisateur. Seul un admin crée d'autres admins |

## Structure (reprise du cours FastAPI)

```
app/
  main.py            création de l'application, montage de l'interface
  core/              configuration (.env), base de données, sécurité, démarrage/arrêt
  api/v1/            agrégation des routes en /api/v1
  routers/           endpoints : auth, jobs, admin, healthz
  services/          logique métier : jobs, stats, purge, authentification
  cruds/             modèles de base et requêtes
  schemas/           objets d'entrée/sortie de l'API (Pydantic)
  ressources/        client du service IA (HttpAIClient) et IA simulée (FakeAIClient)
frontend/            interface web (HTML/CSS/JS, sans dépendance externe)
tests/               tests pytest (IA simulée instantanée, faux serveur HTTP)
```

## Service IA

`HttpAIClient` envoie le média au service IA (`AI_SERVICE_URL`), télécharge le résultat,
puis demande au service d'effacer ses copies. Une erreur du service (injoignable, saturé,
échec) marque le traitement « échoué » avec un message clair.
`MAX_CONCURRENT_JOBS` doit être égal au `NUM_WORKERS` du service IA.

Pour brancher une autre IA : une classe qui respecte le contrat `AIClient.process(...)`
dans `app/ressources/_ai_client.py`, sélectionnée dans `get_ai_client()` via `AI_BACKEND`.

# Service IA de sous-titrage

Service séparé, hébergé sur le serveur GPU, qui transcrit avec Whisper (faster-whisper)
et produit les 4 sorties. Il n'est appelé que par l'application web (`subtitle_app`).

- **Option A** : `NUM_WORKERS` processus, chacun avec sa copie du modèle chargée au démarrage.
  Les traitements tournent en même temps, sans file d'attente : au-delà, réponse 429.
- **Vidéo** : incrustation encodée par NVENC (puce vidéo NVIDIA), repli automatique sur le CPU.
  La piste de sous-titres est ajoutée sans réencodage.
- Un worker qui plante est recréé ; le traitement concerné est signalé en échec.

## Installation

Prérequis : Python 3.11+, ffmpeg dans le PATH, une carte NVIDIA avec CUDA 12.

```bash
cd ai_service
pip install -r requirements.txt
cp .env.example .env
```

Sous Windows, ajouter les bibliothèques CUDA (fournies par l'image Docker sous Linux) :

```bash
pip install nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
```

Le modèle (~1,5 Go pour `medium.en`) est téléchargé au premier démarrage.

## Lancer

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

Le service n'accepte des requêtes qu'une fois tous les modèles chargés (quelques secondes).

## API

| Route | Rôle |
|---|---|
| `POST /v1/jobs` (multipart : `file`, `output_type`) | Traite le média et répond à la fin : texte, nom du fichier produit, durées |
| `GET /v1/jobs/{id}/files/{nom}` | Télécharge le fichier produit |
| `DELETE /v1/jobs/{id}` | Supprime les fichiers du traitement (sinon purge après `RESULT_TTL_HOURS`) |
| `GET /healthz` | État : modèle, nombre de workers, traitements en cours |

`output_type` : `video_embedded`, `video_metadata`, `subtitles` ou `text`.
Un `.wav` ne peut donner que `subtitles` ou `text`.

## Tests

```bash
python -m pytest
```

Les tests n'ont pas besoin de GPU (transcription simulée) mais utilisent le vrai ffmpeg.

## Structure

```
app/config.py       réglages (.env)
app/media.py        ffmpeg : audio, incrustation, piste de sous-titres
app/subtitles.py    .srt et texte
app/transcriber.py  workers Whisper (option A) et transcription simulée
app/pipeline.py     transcription puis sortie demandée
app/main.py         routes de l'API
```

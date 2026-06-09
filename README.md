# Django Movie Survey App

Flow implemented:
1. Consent form (explicit webcam recording notice)
2. Movie carousel (IMDb-style set of movies)
3. Click movie -> description appears immediately
4. Full-screen detail + review view (SST-labeled; powered by `pytreebank` when available)
5. Webcam clips uploaded in the background after consent

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py shell < setup_users.py
python manage.py runserver
```

Open: `http://127.0.0.1:8000/`

## Notes

- Default DB is SQLite (`db.sqlite3`).
- Webcam clips are stored under `media/webcam_clips/`.
- Screen clips are stored under `media/screen_clips/`.
- Temporary recording chunks are accumulated under `media/tmp_recordings/` and finalized to MP4.
- If `pytreebank` loads successfully, movie reviews are sampled from SST "very positive" and
  "very negative" sentences; otherwise static fallback reviews are used.
- If you want SQL Server later, change `DATABASES` in `survey_project/settings.py` to use `mssql-django`.

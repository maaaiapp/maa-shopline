# MAA × SHOPLINE backend

Independent backend for the MAA × SHOPLINE iOS app. Shares no runtime with MAA OS.

```
pip install -r requirements.txt
cp .env.example .env   # fill locally, never commit
python -m pytest -q    # 81 tests incl. RLS on local Postgres 16
uvicorn "app.main:create_app" --factory
```
Status and blockers: `docs/release-readiness.md`.

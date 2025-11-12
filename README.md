# AI-Powered Intrusion Detection System (IDS)

Short description
- A full-stack project for intrusion detection using the KDD dataset, with preprocessing, model training, a Python backend API, and a TypeScript/React frontend.

Repository layout
- backend/
  - [app.py](backend/app.py) — Flask API server that exposes model endpoints.
  - [url_kdd.py](backend/url_kdd.py) — KDD label / URL helpers.
  - [requirements.txt](backend/requirements.txt) — Python dependencies.
  - model/
    - [train_model.py](backend/model/train_model.py) — training script for the ML model.
  - utils/
    - [preprocessing.py](backend/utils/preprocessing.py) — data cleaning & feature engineering utilities.
  - data/
    - [KDDTrain+.txt](backend/data/KDDTrain+.txt) — training dataset (KDD).
    - [KDDTest+.txt](backend/data/KDDTest+.txt) — test dataset (KDD).
  - notebooks/
    - [phase2_preprocessing.ipynb](backend/notebooks/phase2_preprocessing.ipynb) — exploratory preprocessing notebook.
- frontend/ — React + Vite frontend (TypeScript).
  - [package.json](frontend/package.json) — frontend scripts & dependencies.
  - [src/App.tsx](frontend/src/App.tsx) — main UI entry.

Recommended high-level flow
1. Prepare environment
   - Create Python virtualenv and install backend deps: `pip install -r backend/requirements.txt`
   - Install frontend deps: `cd frontend && npm install` (or use bun/pnpm if preferred)
2. Data preprocessing
   - Use the preprocessing utilities: see [backend/utils/preprocessing.py](backend/utils/preprocessing.py) and the notebook [backend/notebooks/phase2_preprocessing.ipynb](backend/notebooks/phase2_preprocessing.ipynb).
   - Input files: [backend/data/KDDTrain+.txt](backend/data/KDDTrain+.txt) and [backend/data/KDDTest+.txt](backend/data/KDDTest+.txt).
3. Model training
   - Run the training script: `python backend/model/train_model.py`
   - Save model artifacts (checkpoint, scaler, label mappings) into `backend/model/` or `backend/artifacts/`.
4. Backend serving
   - Ensure model artifacts are loaded by the API.
   - Run server: `python backend/app.py`
   - Inspect routing & KDD label helpers in [backend/url_kdd.py](backend/url_kdd.py).
5. Frontend integration
   - Start dev UI: `cd frontend && npm run dev`
   - Frontend should call backend endpoints (see [frontend/src/App.tsx](frontend/src/App.tsx)) to submit features and display predictions.
6. Evaluate & iterate
   - Use the test dataset to compute metrics (accuracy, precision, recall, F1).
   - Log experiments and tune preprocessing / model hyperparameters.

Quick start (commands)
- Backend
  - python venv:
    - windows: `python -m venv .venv && .venv\Scripts\activate`
    - mac/linux: `python -m venv .venv && source .venv/bin/activate`
  - install: `pip install -r backend/requirements.txt`
  - train (optional): `python backend/model/train_model.py`
  - run server: `python backend/app.py`
- Frontend
  - install: `cd frontend && npm install`
  - run dev: `npm run dev`
  - build for production: `npm run build`





References (open files)
- [backend/app.py](backend/app.py)
- [backend/url_kdd.py](backend/url_kdd.py)
- [backend/requirements.txt](backend/requirements.txt)
- [backend/model/train_model.py](backend/model/train_model.py)
- [backend/utils/preprocessing.py](backend/utils/preprocessing.py)
- [backend/data/KDDTrain+.txt](backend/data/KDDTrain+.txt)
- [backend/data/KDDTest+.txt](backend/data/KDDTest+.txt)
- [backend/notebooks/phase2_preprocessing.ipynb](backend/notebooks/phase2_preprocessing.ipynb)
- [frontend/package.json](frontend/package.json)
- [frontend/src/App.tsx](frontend/src/App.tsx)
# AI-Powered Intrusion Detection System (IDS)

A full-stack, machine-learning-based Network Intrusion Detection System
(IDS) prototype that captures live network flows, extracts flow-level
features, classifies traffic as **Normal** or **Probe**, records
detection history, and generates persistent alerts through a Flask
backend and React frontend.

> **Current project status:** The project has evolved from the original
> NSL-KDD/URL-oriented prototype into a live network-flow IDS prototype.
> The current deployed detection pipeline uses 27 flow-level features
> and a Random Forest model for binary `normal` vs `probe`
> classification.

------------------------------------------------------------------------

## 1. Project Overview

The system is designed to demonstrate an end-to-end IDS workflow:

``` text
Real Network Traffic
        |
        v
Scapy Packet Capture
        |
        v
Bidirectional Flow Construction
        |
        v
27 Flow-Level Features
        |
        v
Random Forest ML Pipeline
        |
        v
Normal / Probe + Confidence
        |
        +-------------------+
        |                   |
        v                   v
Prediction History       Alert System
                            |
                            v
                      Persistent alerts.json
                            |
                            v
                       React Dashboard
```

The current implementation is intended as a **controlled research/demo
prototype**, not as a production security appliance.

------------------------------------------------------------------------

# 2. Current Detection Scope

## Supported classes

The current live model supports:

-   `normal`
-   `probe`

The original NSL-KDD workflow contained multiple attack categories, but
the current live-flow model was redesigned around a smaller, directly
measurable classification problem.

## Current capture interface

The live capture implementation currently uses the Windows Npcap
loopback interface:

``` text
\Device\NPF_Loopback
```

This means the current live demonstration primarily observes traffic
generated through the local machine's loopback interface, such as:

``` text
127.0.0.1 <-> 127.0.0.1
```

It does **not** currently claim to monitor all Wi-Fi/Ethernet/Internet
traffic.

------------------------------------------------------------------------

# 3. What the IDS Captures

Scapy captures IP/TCP/UDP packets and groups packets belonging to the
same bidirectional connection into a network flow.

Conceptually:

``` text
Packet 1
Packet 2
Packet 3
Packet 4
   |
   v
One network flow
   |
   v
Feature extraction
   |
   v
ML prediction
```

For each flow, the system calculates:

-   duration
-   source port
-   destination port
-   forward packet count
-   backward packet count
-   forward bytes
-   backward bytes
-   total packets
-   total bytes
-   packets per second
-   bytes per second
-   mean packet size
-   minimum packet size
-   maximum packet size
-   packet-size standard deviation
-   SYN count
-   ACK count
-   FIN count
-   RST count
-   PSH count
-   forward packet ratio
-   backward packet ratio
-   forward byte ratio
-   backward byte ratio
-   SYN ratio
-   RST ratio
-   protocol

These are the 27 features expected by the current live-flow model.

------------------------------------------------------------------------

# 4. Current Testing Strategy

The current project uses a controlled local test environment.

## Normal traffic

Normal local application traffic can be captured through the loopback
interface.

For example:

``` text
Browser / Local Application
          |
          v
      127.0.0.1
          |
          v
     Local Service
          |
          v
       Scapy
          |
          v
       IDS Model
          |
          v
       NORMAL
```

## Controlled Probe traffic

The project includes controlled localhost probing of ports in the range:

``` text
8000 - 8049
```

The purpose is to create a reproducible Probe-like traffic pattern
without targeting external systems.

Conceptually:

``` text
127.0.0.1:temporary_port
          |
          +----> 127.0.0.1:8000
          +----> 127.0.0.1:8001
          +----> 127.0.0.1:8002
          ...
          +----> 127.0.0.1:8049
```

The generated flows can then be captured and classified by the model.

> All testing should remain limited to systems and traffic that you own
> or are explicitly authorized to test.

------------------------------------------------------------------------

# 5. Repository Layout

``` text
AI_IDS/
│
├── backend/
│   │
│   ├── app.py
│   ├── url_kdd.py
│   ├── clean_dataset.py
│   ├── inspect_dataset.py
│   ├── evaluate_model.py
│   ├── requirements.txt
│   │
│   ├── data/
│   │   ├── KDDTrain+.txt
│   │   ├── KDDTest+.txt
│   │   ├── live_flows.csv
│   │   ├── live_flows_unlabeled.csv
│   │   └── test_flows.csv
│   │
│   ├── model/
│   │   ├── train_model.py
│   │   ├── model.pkl
│   │   └── preprocessor.pkl
│   │
│   ├── notebooks/
│   │   └── phase2_preprocessing.ipynb
│   │
│   └── utils/
│       └── preprocessing.py
│
└── frontend/
    │
    ├── package.json
    │
    └── src/
        ├── App.jsx
        ├── pages/
        │   ├── Dashboard.jsx
        │   ├── Monitor.jsx
        │   ├── Insights.jsx
        │   ├── Alerts.jsx
        │   └── Settings.jsx
        │
        └── lib/
            └── api.js
```

Depending on the local project state, additional generated/runtime files
may also exist.

------------------------------------------------------------------------

# 6. Backend Components

## `backend/app.py`

Flask API server.

Current responsibilities include:

-   loading the trained ML pipeline
-   receiving manual predictions
-   capturing live network flows
-   predicting captured flows
-   maintaining prediction history
-   creating alerts
-   persisting alerts to `data/alerts.json`
-   updating alert status
-   exposing model/evaluation information
-   exposing traffic statistics
-   reading/updating settings
-   reloading model artifacts

### Main API endpoints

  -----------------------------------------------------------------------
  Endpoint                Method                  Purpose
  ----------------------- ----------------------- -----------------------
  `/`                     GET                     Backend health check

  `/predict`              POST                    Predict from manually
                                                  supplied 27 features

  `/capture`              POST                    Capture live flows and
                                                  classify them

  `/monitor/history`      GET                     Return recent
                                                  prediction history

  `/alerts`               GET                     Return alerts

  `/alerts/<id>`          PATCH                   Update alert status

  `/settings`             GET                     Return IDS settings

  `/settings`             POST                    Update IDS settings

  `/insights/metrics`     GET                     Return independent
                                                  test-set metrics

  `/insights/confusion`   GET                     Return independent
                                                  test-set confusion
                                                  matrix

  `/insights/traffic`     GET                     Return live prediction
                                                  counts

  `/model/retrain`        POST                    Currently reports that
                                                  retraining is not
                                                  implemented

  `/model/reload`         POST                    Reload model artifacts

  `/model/reset`          POST                    Reset settings and
                                                  reload model
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 7. Live Capture Endpoint

The current live capture endpoint is:

``` text
POST /capture
```

Example:

``` powershell
Invoke-RestMethod `
    -Uri "http://127.0.0.1:5000/capture" `
    -Method POST `
    -ContentType "application/json" `
    -Body '{"capture_time":5}'
```

The backend:

1.  validates the requested capture duration
2.  captures network packets
3.  constructs bidirectional flows
4.  converts each flow into the 27-feature representation
5.  sends the feature vector through the saved ML pipeline
6.  obtains the prediction and confidence
7.  records the prediction
8.  creates an alert when appropriate
9.  returns the analyzed flows as JSON

Example response structure:

``` json
{
  "message": "Network capture and detection completed",
  "flows_captured": 1,
  "flows": [
    {
      "features": {
        "duration": 0.03,
        "source_port": 55818,
        "destination_port": 49350,
        "forward_packets": 5,
        "backward_packets": 4,
        "forward_bytes": 41320,
        "backward_bytes": 188,
        "total_packets": 9,
        "total_bytes": 41508,
        "protocol": "tcp"
      },
      "prediction": "normal",
      "confidence": 0.8533,
      "timestamp": "YYYY-MM-DD HH:MM:SS"
    }
  ]
}
```

The exact feature values depend on the captured traffic.

------------------------------------------------------------------------

# 8. Machine Learning Model

The current saved model is a scikit-learn Random Forest pipeline.

The important implementation detail is that the saved `model.pkl`
already contains the required preprocessing pipeline.

Therefore prediction is performed directly with:

``` python
prediction = model.predict(features_df)[0]

confidence = float(
    np.max(
        model.predict_proba(features_df)
    )
)
```

The frontend/backend should not manually apply the saved preprocessor
before passing data into this pipeline.

------------------------------------------------------------------------

# 9. Current Model Evaluation

The current independent test set contains:

``` text
52 samples
27 Probe
25 Normal
```

The measured independent evaluation was approximately:

``` text
Accuracy : 98.08%
Precision: 98.00%
Recall   : 98.00%
F1 Score : 98.00%
```

Confusion matrix:

``` text
                 Predicted
               Normal  Probe

Actual Normal     24      1

Actual Probe       0     27
```

### Important interpretation

These numbers come from a **controlled independent localhost test set**.

They should **not** be presented as:

-   98% production accuracy
-   98% accuracy on arbitrary Internet traffic
-   proof that the IDS detects all real-world attacks

The current dataset is relatively small and controlled, and the Probe
traffic is highly uniform. More diverse traffic and evaluation against
genuinely independent scenarios are needed before making stronger
performance claims.

------------------------------------------------------------------------

# 10. Frontend

The frontend is a React application.

## Dashboard

The Dashboard currently displays:

-   monitoring activity
-   prediction counts
-   alerts
-   traffic information

The live traffic classification uses:

``` text
Normal
Probe
```

rather than the older `Attack` terminology.

## Monitor

The Monitor page supports:

### Manual feature prediction

A user can enter the 27 live-flow features and submit them to
`/predict`.

### Controlled Probe test

The page can load a predefined Probe-like feature vector for repeatable
testing.

### Live capture

The `Capture & Detect` button calls:

``` text
POST /capture
```

and displays captured flow predictions.

### Continuous monitoring

The page can start and stop repeated capture cycles.

The current implementation performs a capture approximately every 10
seconds while monitoring is enabled, with each capture lasting
approximately 5 seconds.

## Insights

The Insights page displays:

-   independent test-set model performance
-   confusion matrix
-   live traffic counts

The confusion matrix uses:

``` text
Normal
Probe
```

terminology.

## Alerts

The Alerts page displays generated IDS alerts and supports:

-   Mark as Reviewed
-   False Positive

Alert state is persisted in:

``` text
backend/data/alerts.json
```

------------------------------------------------------------------------

# 11. Alert Logic

An alert is generated when:

``` text
prediction != normal
```

and the confidence exceeds the configured sensitivity threshold.

The default backend setting is:

``` python
"sensitivity_threshold": 75
```

The threshold is expressed as a percentage.

For example:

``` text
prediction = probe
confidence = 0.85
threshold  = 75
```

results in an alert because:

``` text
85% >= 75%
```

------------------------------------------------------------------------

# 12. Settings

Current settings include:

``` python
{
    "live_detection": True,
    "ml_model": "random-forest",
    "sensitivity_threshold": 75,
    "auto_retrain": False,
    "email_alerts": True,
    "desktop_notifications": True
}
```

Some UI settings are currently configuration placeholders rather than
complete external notification integrations.

------------------------------------------------------------------------

# 13. Installation

## Backend

Create a Python virtual environment.

### Windows

``` powershell
python -m venv .venv
.venv\Scripts\activate
```

### macOS/Linux

``` bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

``` bash
pip install -r backend/requirements.txt
```

If working from inside the backend directory:

``` bash
cd backend
pip install -r requirements.txt
```

------------------------------------------------------------------------

# 14. Running the Backend

From the project root:

``` bash
python backend/app.py
```

The Flask server runs on:

``` text
http://127.0.0.1:5000
```

Health check:

``` text
GET http://127.0.0.1:5000/
```

Expected response:

``` json
{
  "message": "Intrusion Detection API Running!"
}
```

------------------------------------------------------------------------

# 15. Running the Frontend

From the frontend directory:

``` bash
cd frontend
npm install
npm run dev
```

The development server is typically available at a localhost address
such as:

``` text
http://localhost:8081
```

The exact port depends on the frontend development configuration.

------------------------------------------------------------------------

# 16. Testing the Live Capture

Make sure the backend is running.

Then:

``` powershell
Invoke-RestMethod `
    -Uri "http://127.0.0.1:5000/capture" `
    -Method POST `
    -ContentType "application/json" `
    -Body '{"capture_time":5}'
```

For a more readable PowerShell result:

``` powershell
$response = Invoke-RestMethod `
    -Uri "http://127.0.0.1:5000/capture" `
    -Method POST `
    -ContentType "application/json" `
    -Body '{"capture_time":5}'

$response.flows | Format-List
```

------------------------------------------------------------------------

# 17. Testing the Frontend

Open the frontend and navigate to:

``` text
Network Monitor
```

### Manual test

1.  Click `Load Probe Test`
2.  Click `Predict Manual Features`
3.  Observe the prediction and confidence

### Live test

1.  Click `Capture & Detect`
2.  Wait for the capture to complete
3.  Review the detected flows
4.  Review prediction history
5.  Check Alerts if a non-normal flow exceeds the confidence threshold

### Continuous test

1.  Click `Start Monitoring`
2.  Allow several capture cycles to run
3.  Observe history and live captured-flow results
4.  Click `Stop Monitoring`

------------------------------------------------------------------------

# 18. Data Collection

The project includes live-flow CSV collection utilities.

The current labeled live dataset contains examples of:

``` text
normal
probe
```

The dataset can be inspected using:

``` bash
python backend/inspect_dataset.py
```

The controlled labeling/cleaning workflow can be run using:

``` bash
python backend/clean_dataset.py
```

The exact dataset size and distribution may change as additional traffic
is collected.

------------------------------------------------------------------------

# 19. Independent Evaluation

The independent evaluation script is:

``` bash
python backend/evaluate_model.py
```

It uses the saved model and the independent flow test dataset.

The evaluation checks:

-   accuracy
-   precision
-   recall
-   F1 score
-   confusion matrix

The evaluation script performs prediction using the saved model pipeline
without fitting the model during evaluation.

------------------------------------------------------------------------

# 20. Model Training

The training script is:

``` bash
python backend/model/train_model.py
```

The current model artifacts include:

``` text
backend/model/model.pkl
backend/model/preprocessor.pkl
```

Before retraining, ensure the training data and feature schema match the
current live-flow feature definition.

The backend currently does not expose automatic model retraining.

The `/model/retrain` endpoint intentionally reports that retraining is
not implemented rather than pretending that a retraining operation
occurred.

------------------------------------------------------------------------

# 21. Original KDD Dataset Components

The repository still contains the original NSL-KDD-related files:

``` text
backend/data/KDDTrain+.txt
backend/data/KDDTest+.txt
backend/url_kdd.py
backend/notebooks/phase2_preprocessing.ipynb
```

These are retained as project history / research material.

However, the current live IDS path is based on the live-flow feature
representation rather than directly treating a URL as the model input.

This distinction is important:

``` text
Original prototype:
URL/KDD-oriented workflow

Current live IDS:
Network packets
    ↓
Network flows
    ↓
27 flow features
    ↓
ML classification
```

------------------------------------------------------------------------

# 22. Limitations

The current prototype has several important limitations.

## 22.1 Limited classes

The live model currently distinguishes:

``` text
Normal vs Probe
```

It does not currently provide a complete multi-class intrusion taxonomy.

## 22.2 Small controlled dataset

The live dataset is currently small compared with datasets normally used
for robust network intrusion research.

## 22.3 Controlled Probe traffic

The current Probe traffic is highly structured and repetitive,
especially around the localhost port range used for collection.

This can make evaluation appear stronger than performance on varied
real-world traffic.

## 22.4 Loopback capture

The current capture interface is the Windows Npcap loopback interface.

Therefore the current implementation is not equivalent to a network-wide
IDS monitoring a Wi-Fi or Ethernet adapter.

## 22.5 Flow-duration edge cases

Very short flows can produce extremely large calculated packet/byte
rates because:

``` text
rate = quantity / duration
```

A future version should consider sensible handling or clipping of
extreme rate values.

## 22.6 In-memory prediction history

Prediction history currently exists in application memory and can be
lost when Flask restarts.

Alerts are persisted separately in `alerts.json`.

## 22.7 Production hardening

The current application is a prototype and does not yet provide the
security, concurrency, authentication, database, deployment, and
operational hardening expected from a production IDS.

------------------------------------------------------------------------

# 23. Research / Project Demonstration Flow

A clean demonstration can follow this sequence:

``` text
1. Start Flask backend
        |
2. Start React frontend
        |
3. Open Network Monitor
        |
4. Show live capture
        |
5. Capture normal localhost traffic
        |
6. Show Normal prediction
        |
7. Generate controlled local Probe traffic
        |
8. Capture again
        |
9. Show Probe prediction
        |
10. Show confidence
        |
11. Show prediction history
        |
12. Show generated alert
        |
13. Open Insights
        |
14. Explain independent evaluation
```

This demonstrates the complete system without making unsupported claims
about Internet-wide or production attack detection.

------------------------------------------------------------------------

# 24. Future Improvements

The strongest next improvements are:

1.  Increase the diversity and size of the live-flow dataset.
2.  Reduce dependence on destination-port patterns.
3.  Add more controlled abnormal traffic categories.
4.  Improve ground-truth labeling.
5.  Add richer flow identifiers and source/destination information.
6.  Handle very short-duration flows more robustly.
7.  Persist prediction history in a database.
8.  Improve alert deduplication and lifecycle management.
9.  Add proper model/version metadata.
10. Add an explicit capture-interface selector.
11. Support authorized Wi-Fi/Ethernet monitoring for controlled lab
    environments.
12. Add better real-time visualizations.
13. Add automated retraining only after a reliable labeled-data workflow
    exists.
14. Evaluate on multiple independent traffic scenarios rather than a
    single controlled test set.

------------------------------------------------------------------------

# 25. Important Project Claim

The current project should be described as:

> **A full-stack machine-learning-based network intrusion detection
> prototype that captures local network flows, extracts 27 flow-level
> statistical and TCP features, and classifies traffic as Normal or
> Probe using a Random Forest pipeline, with real-time monitoring,
> prediction history, and persistent alerts.**

Avoid describing the current implementation as a complete
production-grade IDS or as a validated detector for arbitrary Internet
attacks.

------------------------------------------------------------------------

# 26. Quick Start

From the project root:

### Backend

``` powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/requirements.txt
python backend/app.py
```

### Frontend

Open another terminal:

``` powershell
cd frontend
npm install
npm run dev
```

Then open the frontend URL shown by Vite.

### Live detection

Navigate to:

``` text
Network Monitor
```

and click:

``` text
Capture & Detect
```

or:

``` text
Start Monitoring
```

------------------------------------------------------------------------

# 27. Summary

The current system provides an end-to-end IDS prototype:

``` text
             NETWORK
                |
                v
        +---------------+
        | Packet Capture|
        |    Scapy      |
        +-------+-------+
                |
                v
        +---------------+
        | Flow Builder  |
        +-------+-------+
                |
                v
        +---------------+
        | 27 Features   |
        +-------+-------+
                |
                v
        +---------------+
        | Random Forest |
        +-------+-------+
                |
          +-----+-----+
          |           |
          v           v
       NORMAL       PROBE
          |           |
          +-----+-----+
                |
                v
       History / Alerts
                |
                v
        React Dashboard
```

The system is currently best suited for **controlled local
experimentation, demonstration, and continued IDS research
development**.

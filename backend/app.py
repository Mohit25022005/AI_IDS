from flask import Flask, request, jsonify
from flask_cors import CORS
import joblib
import numpy as np
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, 'model')

# ---------------- Default Settings ----------------
settings = {
    "live_detection": True,
    "ml_model": "random-forest",
    "sensitivity_threshold": 75,
    "auto_retrain": False,
    "email_alerts": True,
    "desktop_notifications": True,
}

# ---------------- In-Memory Storage ----------------
prediction_history = []  # Store last N predictions
alerts_data = []        # Store threat alerts

# ---------------- Load Model ----------------
def load_model(model_file='model.pkl', scaler_file='scaler.pkl'):
    model_path = os.path.join(MODEL_DIR, model_file)
    scaler_path = os.path.join(MODEL_DIR, scaler_file)
    if not os.path.exists(model_path) or not os.path.exists(scaler_path):
        return None, None
    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    return model, scaler

model, scaler = load_model()

# ---------------- Home ----------------
@app.route('/')
def home():
    return jsonify({"message": "Intrusion Detection API Running!"})

# ---------------- Prediction ----------------
@app.route('/predict', methods=['POST'])
def predict():
    global prediction_history, alerts_data

    if model is None or scaler is None:
        return jsonify({"error": "Model not loaded"}), 500

    data = request.get_json(silent=True)
    if not data or 'features' not in data:
        return jsonify({"error": "Missing 'features' in request body"}), 400

    raw_input = data['features']

    # Accept either list of numbers or comma-separated string of numbers
    if isinstance(raw_input, str):
        raw_list = [x.strip() for x in raw_input.split(',')]
    elif isinstance(raw_input, list):
        raw_list = raw_input
    else:
        return jsonify({"error": "Invalid input type"}), 400

    # Convert all values to float
    numeric_features = []
    for val in raw_list[:41]:  # Only first 41 numeric features
        try:
            numeric_features.append(float(val))
        except:
            numeric_features.append(0.0)

    # Validate feature count
    if len(numeric_features) != model.n_features_in_:
        return jsonify({
            "error": f"Expected {model.n_features_in_} numeric features, got {len(numeric_features)}"
        }), 400

    features = np.array(numeric_features).reshape(1, -1)
    features_scaled = scaler.transform(features)

    prediction = model.predict(features_scaled)[0]
    confidence = float(np.max(model.predict_proba(features_scaled)))
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Store in history
    prediction_history.append({
        "timestamp": timestamp,
        "prediction": prediction,
        "confidence": confidence
    })

    # Generate alert if attack
    if prediction.lower() == "attack" and confidence * 100 >= settings["sensitivity_threshold"]:
        alerts_data.append({
            "id": len(alerts_data) + 1,
            "timestamp": timestamp,
            "type": "Intrusion Detected",
            "severity": "high",
            "sourceIP": "N/A",
            "description": f"Attack detected with confidence {confidence*100:.1f}%",
            "status": "active"
        })

    return jsonify({
        "prediction": prediction,
        "confidence": confidence,
        "features_used": len(numeric_features)
    })

# ---------------- Monitor History ----------------
@app.route("/monitor/history")
def monitor_history():
    return jsonify(prediction_history[-50:])

# ---------------- Alerts ----------------
@app.route("/alerts")
def get_alerts():
    return jsonify(alerts_data[-50:])

# ---------------- Settings ----------------
@app.route('/settings', methods=['GET'])
def get_settings():
    return jsonify(settings)

@app.route('/settings', methods=['POST'])
def update_settings():
    global settings
    data = request.json
    for key in data:
        if key in settings:
            settings[key] = data[key]
    return jsonify({"message": "Settings updated successfully", "settings": settings})

# ---------------- Model Management ----------------
@app.route('/model/retrain', methods=['POST'])
def retrain_model():
    return jsonify({"message": "Model retraining started (simulation)"}), 200

@app.route('/model/reload', methods=['POST'])
def reload_model():
    global model, scaler
    model, scaler = load_model()
    if model is None or scaler is None:
        return jsonify({"error": "Failed to reload model"}), 500
    return jsonify({"message": "Model reloaded successfully"}), 200

@app.route('/model/reset', methods=['POST'])
def reset_model_defaults():
    global settings, model, scaler
    settings = {
        "live_detection": True,
        "ml_model": "random-forest",
        "sensitivity_threshold": 75,
        "auto_retrain": False,
        "email_alerts": True,
        "desktop_notifications": True,
    }
    model, scaler = load_model()
    return jsonify({"message": "Model and settings reset to defaults", "settings": settings}), 200

# ---------------- Insights -----------------
@app.route("/insights/metrics")
def insights_metrics():
    return jsonify({
        "accuracy": 98.7,
        "precision": 97.3,
        "recall": 96.8,
        "f1": 97.0
    })

@app.route("/insights/confusion")
def insights_confusion():
    return jsonify([
        [450, 12],
        [15, 523]
    ])

@app.route("/insights/traffic")
def insights_traffic():
    return jsonify([
        {"name": "Normal", "count": 470},
        {"name": "Attack", "count": 550}
    ])

# ---------------- Run App ----------------
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

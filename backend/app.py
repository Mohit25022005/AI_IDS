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

    data = request.get_json()
    features = np.array(data['features']).reshape(1, -1)
    scaled_features = scaler.transform(features)
    prediction = model.predict(scaled_features)[0]
    confidence = float(np.max(model.predict_proba(scaled_features)))
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Store in history
    prediction_history.append({
        "timestamp": timestamp,
        "prediction": prediction,
        "confidence": confidence
    })

    # Generate alert if attack detected and above sensitivity threshold
    if prediction.lower() == "attack" and confidence*100 >= settings["sensitivity_threshold"]:
        alerts_data.append({
            "id": len(alerts_data)+1,
            "timestamp": timestamp,
            "type": "Intrusion Detected",
            "severity": "high",
            "sourceIP": "N/A",
            "description": f"Attack detected with confidence {confidence*100:.1f}%",
            "status": "active"
        })

    return jsonify({"prediction": prediction, "confidence": confidence})

# ---------------- Monitor History ----------------
@app.route("/monitor/history")
def monitor_history():
    return jsonify(prediction_history[-50:])  # Last 50 predictions

# ---------------- Alerts ----------------
@app.route("/alerts")
def get_alerts():
    return jsonify(alerts_data[-50:])  # Last 50 alerts

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

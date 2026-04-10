from flask import Flask, request, jsonify
from flask_cors import CORS
import joblib
import numpy as np
import os
from datetime import datetime

from url_kdd import generate_kdd_features_from_url

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, 'model')

# ---------------- Feature Names ----------------
FEATURE_COLUMNS = [
    'duration', 'protocol_type', 'service', 'flag', 'src_bytes', 'dst_bytes',
    'land', 'wrong_fragment', 'urgent', 'hot', 'num_failed_logins', 'logged_in',
    'num_compromised', 'root_shell', 'su_attempted', 'num_root',
    'num_file_creations', 'num_shells', 'num_access_files', 'num_outbound_cmds',
    'is_host_login', 'is_guest_login', 'count', 'srv_count',
    'serror_rate', 'srv_serror_rate', 'rerror_rate', 'srv_rerror_rate',
    'same_srv_rate', 'diff_srv_rate', 'srv_diff_host_rate',
    'dst_host_count', 'dst_host_srv_count', 'dst_host_same_srv_rate',
    'dst_host_diff_srv_rate', 'dst_host_same_src_port_rate',
    'dst_host_srv_diff_host_rate', 'dst_host_serror_rate',
    'dst_host_srv_serror_rate', 'dst_host_rerror_rate',
    'dst_host_srv_rerror_rate'
]

# ---------------- Settings ----------------
settings = {
    "live_detection": True,
    "ml_model": "random-forest",
    "sensitivity_threshold": 75,
    "auto_retrain": False,
    "email_alerts": True,
    "desktop_notifications": True,
}

prediction_history = []
alerts_data = []

# ---------------- Load Model ----------------
def load_model():
    model_path = os.path.join(MODEL_DIR, 'model.pkl')
    scaler_path = os.path.join(MODEL_DIR, 'scaler.pkl')

    if not os.path.exists(model_path) or not os.path.exists(scaler_path):
        return None, None

    return joblib.load(model_path), joblib.load(scaler_path)

model, scaler = load_model()

# ---------------- Routes ----------------
@app.route('/')
def home():
    return jsonify({"message": "Intrusion Detection API Running!"})


@app.route('/predict', methods=['POST'])
def predict():
    global prediction_history, alerts_data

    if model is None or scaler is None:
        return jsonify({"error": "Model not loaded"}), 500

    data = request.get_json(silent=True)
    features_input = data.get('features')
    url_input = data.get('url')

    numeric_features = []

    # -------- Input Handling --------
    if features_input:
        raw_list = features_input if isinstance(features_input, list) else features_input.split(',')

        for val in raw_list[:41]:
            try:
                numeric_features.append(float(val))
            except:
                numeric_features.append(0.0)

    elif url_input:
        try:
            numeric_features = generate_kdd_features_from_url(url_input)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify({"error": "Provide 'features' or 'url'"}), 400

    # -------- Feature Mapping --------
    features_named = dict(zip(FEATURE_COLUMNS, numeric_features))

    # -------- Model Prediction --------
    features_arr = np.array(numeric_features).reshape(1, -1)
    features_scaled = scaler.transform(features_arr)

    prediction = model.predict(features_scaled)[0]
    confidence = float(np.max(model.predict_proba(features_scaled)))

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # -------- Store History --------
    prediction_history.append({
        "timestamp": timestamp,
        "prediction": prediction,
        "confidence": confidence
    })

    # -------- Alerts --------
    if prediction.lower() == "attack" and confidence * 100 >= settings["sensitivity_threshold"]:
        alerts_data.append({
            "id": len(alerts_data) + 1,
            "timestamp": timestamp,
            "type": "Intrusion Detected",
            "severity": "high",
            "description": f"Attack detected ({confidence*100:.1f}%)",
            "status": "active"
        })

    # -------- Interpretation Layer --------
    interpreted = {
        "traffic_volume": features_named["src_bytes"] + features_named["dst_bytes"],
        "connection_count": features_named["count"],
        "service_match_rate": features_named["same_srv_rate"]
    }

    return jsonify({
        "prediction": prediction,
        "confidence": confidence,
        "timestamp": timestamp,
        "features_named": features_named,
        "interpreted": interpreted
    })


@app.route("/monitor/history")
def monitor_history():
    return jsonify(prediction_history[-50:])


@app.route("/alerts")
def get_alerts():
    return jsonify(alerts_data[-50:])


@app.route('/settings', methods=['GET', 'POST'])
def handle_settings():
    global settings
    if request.method == 'POST':
        data = request.json
        for key in data:
            if key in settings:
                settings[key] = data[key]
    return jsonify(settings)


@app.route('/model/reload', methods=['POST'])
def reload_model():
    global model, scaler
    model, scaler = load_model()
    return jsonify({"message": "Model reloaded"})


# ---------------- Run ----------------
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
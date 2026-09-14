from flask import Flask, request, jsonify
from flask_cors import CORS
import joblib
import numpy as np
import pandas as pd
import os
import json
from datetime import datetime
from url_kdd import capture_flows, build_feature_vector

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, 'model')
ALERTS_FILE = os.path.join(
    BASE_DIR,
    "data",
    "alerts.json"
)
# NSL-KDD feature names
LIVE_FEATURE_COLUMNS = [
    "duration",
    "source_port",
    "destination_port",
    "forward_packets",
    "backward_packets",
    "forward_bytes",
    "backward_bytes",
    "total_packets",
    "total_bytes",
    "packets_per_second",
    "bytes_per_second",
    "mean_packet_size",
    "min_packet_size",
    "max_packet_size",
    "packet_size_std",
    "syn_count",
    "ack_count",
    "fin_count",
    "rst_count",
    "psh_count",
    "forward_packet_ratio",
    "backward_packet_ratio",
    "forward_byte_ratio",
    "backward_byte_ratio",
    "syn_ratio",
    "rst_ratio",
    "protocol"
]

# ---------------- Default Settings ----------------
settings = {
    "live_detection": True,
    "ml_model": "random-forest",
    "sensitivity_threshold": 55,
    "auto_retrain": False,
    "email_alerts": True,
    "desktop_notifications": True,
}

# ---------------- In-Memory Storage ----------------
prediction_history = []


def load_alerts():
    if not os.path.exists(ALERTS_FILE):
        return []

    try:
        with open(ALERTS_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, list):
            return data

    except (json.JSONDecodeError, OSError):
        pass

    return []


def save_alerts():
    os.makedirs(
        os.path.dirname(ALERTS_FILE),
        exist_ok=True
    )

    with open(
        ALERTS_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            alerts_data,
            file,
            indent=2
        )


alerts_data = load_alerts()


# ---------------- Load Model ----------------
def load_model(model_file='model.pkl', preprocessor_file='preprocessor.pkl'):
    model_path = os.path.join(MODEL_DIR, model_file)
    preprocessor_path = os.path.join(MODEL_DIR, preprocessor_file)

    if not os.path.exists(model_path) or not os.path.exists(preprocessor_path):
        return None, None

    model = joblib.load(model_path)
    preprocessor = joblib.load(preprocessor_path)

    return model, preprocessor

model, preprocessor = load_model()

# ---------------- Home ----------------
@app.route('/')
def home():
    return jsonify({"message": "Intrusion Detection API Running!"})

# ---------------- Prediction ----------------
@app.route('/predict', methods=['POST'])
def predict():
    global prediction_history, alerts_data

    if model is None or preprocessor is None:
        return jsonify({"error": "Model not loaded"}), 500

    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "error": "Request body must contain JSON data"
        }), 400

    features_input = data.get("features")

    if features_input is None:
        return jsonify({
            "error": "Missing 'features' in request body"
        }), 400

    if not isinstance(features_input, dict):
        return jsonify({
            "error": "'features' must be a JSON object"
        }), 400

    missing_features = [
        feature
        for feature in LIVE_FEATURE_COLUMNS
        if feature not in features_input
    ]

    if missing_features:
        return jsonify({
            "error": "Missing required features",
            "missing_features": missing_features
        }), 400

    extra_features = [
        feature
        for feature in features_input
        if feature not in LIVE_FEATURE_COLUMNS
    ]

    if extra_features:
        return jsonify({
            "error": "Unknown features provided",
            "unknown_features": extra_features
        }), 400

    numeric_features = {}

    for feature in LIVE_FEATURE_COLUMNS:
        if feature == "protocol":
            protocol = str(features_input[feature]).lower()

            if protocol not in ["tcp", "udp", "other"]:
                return jsonify({
                    "error": "protocol must be one of: tcp, udp, other"
                }), 400

            numeric_features[feature] = protocol

        else:
            try:
                numeric_features[feature] = float(
                    features_input[feature]
                )
            except (TypeError, ValueError):
                return jsonify({
                    "error": f"Feature '{feature}' must be numeric"
                }), 400
                
    # Convert validated features into the exact
    # 27-feature DataFrame expected by the preprocessor.
    features_df = pd.DataFrame(
        [numeric_features],
        columns=LIVE_FEATURE_COLUMNS
    )

    # Apply the same preprocessing pipeline used during training.
    prediction = model.predict(features_df)[0]
    confidence = float(
        np.max(
            model.predict_proba(features_df)
        )
    )
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Store prediction history
    prediction_history.append({
        "timestamp": timestamp,
        "prediction": prediction,
        "confidence": confidence
    })

    # Generate alert for any non-normal prediction
    if prediction.lower() != "normal" and confidence * 100 >= settings["sensitivity_threshold"]:
       alerts_data.append({
        "id": len(alerts_data) + 1,
        "timestamp": timestamp,
        "type": "Intrusion Detected",
        "severity": "high",
        "sourceIP": "N/A",
        "description": f"{prediction} activity detected with confidence {confidence*100:.1f}%",
        "status": "active"
    })

    save_alerts()

    return jsonify({
        "prediction": str(prediction),
        "confidence": confidence,
        "timestamp": timestamp,
        "features_used": {
            feature: numeric_features[feature]
            for feature in LIVE_FEATURE_COLUMNS
        }
    })

# ---------------- Live Flow Capture + Prediction ----------------
@app.route("/capture", methods=["POST"])
def capture_network_flows():
    try:
        data = request.get_json(silent=True) or {}

        capture_time = float(
            data.get("capture_time", 8)
        )

        if capture_time <= 0 or capture_time > 60:
            return jsonify({
                "error": "capture_time must be between 0 and 60 seconds"
            }), 400

        if model is None:
            return jsonify({
                "error": "ML model is not loaded"
            }), 500

        flows = capture_flows(
            capture_time=capture_time
        )

        detected_flows = []

        for flow in flows:

            # Convert captured flow into the exact
            # 27-feature format expected by the model
            feature_vector = build_feature_vector(flow)

            features_df = pd.DataFrame(
                [feature_vector],
                columns=LIVE_FEATURE_COLUMNS
            )

            # Predict using the saved Pipeline.
            # The Pipeline handles preprocessing internally.
            prediction = model.predict(features_df)[0]

            confidence = float(
                np.max(
                    model.predict_proba(features_df)
                )
            )

            timestamp = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            # Store prediction in monitoring history
            prediction_history.append({
                "timestamp": timestamp,
                "prediction": str(prediction),
                "confidence": confidence
            })

            # Create an alert for non-normal traffic
            # when confidence crosses the configured threshold
            if (
                str(prediction).lower() != "normal"
                and confidence * 100 >= settings["sensitivity_threshold"]
            ):
                alerts_data.append({
                    "id": len(alerts_data) + 1,
                    "timestamp": timestamp,
                    "type": "Intrusion Detected",
                    "severity": "high",
                    "sourceIP": flow.src_ip,
                    "description": (
                        f"{prediction} activity detected with "
                        f"confidence {confidence * 100:.1f}%"
                    ),
                    "status": "active"
                })

                save_alerts()

            detected_flows.append({
                "features": feature_vector,
                "prediction": str(prediction),
                "confidence": confidence,
                "timestamp": timestamp
            })

        return jsonify({
            "message": "Network capture and detection completed",
            "flows_captured": len(detected_flows),
            "flows": detected_flows
        }), 200

    except Exception as e:
        return jsonify({
            "error": f"Network capture failed: {str(e)}"
        }), 500
        
        
# ---------------- Monitor History ----------------
@app.route("/monitor/history")
def monitor_history():
    return jsonify(prediction_history[-50:])

# ---------------- Alerts ----------------
@app.route("/alerts")
def get_alerts():
    return jsonify(alerts_data[-50:])

@app.route("/alerts/<int:alert_id>", methods=["PATCH"])
def update_alert(alert_id):
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")

    allowed_statuses = {
        "active",
        "reviewed",
        "false-positive"
    }

    if new_status not in allowed_statuses:
        return jsonify({
            "error": "Invalid alert status",
            "allowed_statuses": list(allowed_statuses)
        }), 400

    for alert in alerts_data:
        if alert["id"] == alert_id:
            alert["status"] = new_status

            save_alerts()

            return jsonify({
                "message": "Alert status updated successfully",
                "alert": alert
            }), 200

    return jsonify({
        "error": f"Alert {alert_id} not found"
    }), 404

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
    return jsonify({
        "error": "Model retraining is not implemented yet"
    }), 501
    
@app.route('/model/reload', methods=['POST'])
def reload_model():
    global model, preprocessor

    model, preprocessor = load_model()

    if model is None or preprocessor is None:
        return jsonify({
            "error": "Failed to reload model"
        }), 500

    return jsonify({
        "message": "Model reloaded successfully"
    }), 200
    
@app.route('/model/reset', methods=['POST'])
def reset_model_defaults():
    global settings, model, preprocessor

    settings = {
        "live_detection": True,
        "ml_model": "random-forest",
        "sensitivity_threshold": 75,
        "auto_retrain": False,
        "email_alerts": True,
        "desktop_notifications": True,
    }

    model, preprocessor = load_model()

    if model is None or preprocessor is None:
        return jsonify({
            "error": "Failed to reload model during reset"
        }), 500

    return jsonify({
        "message": "Model and settings reset to defaults",
        "settings": settings
    }), 200

# ---------------- Insights -----------------
@app.route("/insights/metrics")
def insights_metrics():
    return jsonify({
        "accuracy": 98.08,
        "precision": 98.00,
        "recall": 98.00,
        "f1": 98.00,
        "evaluation_type": "independent_test_set",
        "test_samples": 52
    })

@app.route("/insights/confusion")
def insights_confusion():
    return jsonify({
        "labels": ["normal", "probe"],
        "matrix": [
            [24, 1],
            [0, 27]
        ]
    })

@app.route("/insights/traffic")
def insights_traffic():
    normal_count = sum(
        1 for item in prediction_history
        if str(item["prediction"]).lower() == "normal"
    )

    probe_count = sum(
        1 for item in prediction_history
        if str(item["prediction"]).lower() == "probe"
    )

    return jsonify([
        {
            "name": "Normal",
            "count": normal_count
        },
        {
            "name": "Probe",
            "count": probe_count
        }
    ])

# ---------------- Run App ----------------
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

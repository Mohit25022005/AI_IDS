import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score
import joblib
import os

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, '..', 'data')
train_path = os.path.join(DATA_DIR, 'KDDTrain+.txt')
test_path = os.path.join(DATA_DIR, 'KDDTest+.txt')

# Column names from NSL-KDD dataset description
columns = [
    'duration', 'protocol_type', 'service', 'flag', 'src_bytes', 'dst_bytes',
    'land', 'wrong_fragment', 'urgent', 'hot', 'num_failed_logins', 'logged_in',
    'num_compromised', 'root_shell', 'su_attempted', 'num_root', 'num_file_creations',
    'num_shells', 'num_access_files', 'num_outbound_cmds', 'is_host_login',
    'is_guest_login', 'count', 'srv_count', 'serror_rate', 'srv_serror_rate',
    'rerror_rate', 'srv_rerror_rate', 'same_srv_rate', 'diff_srv_rate',
    'srv_diff_host_rate', 'dst_host_count', 'dst_host_srv_count',
    'dst_host_same_srv_rate', 'dst_host_diff_srv_rate',
    'dst_host_same_src_port_rate', 'dst_host_srv_diff_host_rate',
    'dst_host_serror_rate', 'dst_host_srv_serror_rate', 'dst_host_rerror_rate',
    'dst_host_srv_rerror_rate', 'label', 'difficulty'
]

print("📥 Loading data...")
train_df = pd.read_csv(train_path, names=columns)
test_df = pd.read_csv(test_path, names=columns)

# Drop difficulty column
train_df.drop('difficulty', axis=1, inplace=True)
test_df.drop('difficulty', axis=1, inplace=True)

# Combine for consistent encoding
combined = pd.concat([train_df, test_df])

# Label encode categorical columns
cat_cols = ['protocol_type', 'service', 'flag']
encoder = LabelEncoder()
for col in cat_cols:
    combined[col] = encoder.fit_transform(combined[col])

# Split again
train_df = combined.iloc[:len(train_df)]
test_df = combined.iloc[len(train_df):]

# Split features/labels
X_train = train_df.drop('label', axis=1)
y_train = train_df['label']
X_test = test_df.drop('label', axis=1)
y_test = test_df['label']

# Simplify labels to "normal" vs "attack"
y_train = y_train.apply(lambda x: 'normal' if x == 'normal' else 'attack')
y_test = y_test.apply(lambda x: 'normal' if x == 'normal' else 'attack')

# Scale features
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# Train model
print("🚀 Training Random Forest model...")
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train_scaled, y_train)

# Evaluate
preds = model.predict(X_test_scaled)
print("✅ Accuracy:", accuracy_score(y_test, preds))
print(classification_report(y_test, preds))

# Save model + scaler
joblib.dump(model, os.path.join(BASE_DIR, 'model.pkl'))
joblib.dump(scaler, os.path.join(BASE_DIR, 'scaler.pkl'))

print("💾 Model and scaler saved successfully!")

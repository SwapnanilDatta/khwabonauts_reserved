from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler
import pandas as pd
import joblib

# Load your data
df = pd.read_csv('organ_matching_data.csv')

# Feature engineering
df['age_similarity'] = 1 / (1 + abs(df['donor_age'] - df['recipient_age']))
df['distance_score'] = 1 / (1 + df['distance_kg'])
features = df[['age_similarity', 'distance_score', 'urgency_level']]
target = df['compatibility_score']

# Scaling
scaler = MinMaxScaler()
features_scaled = scaler.fit_transform(features)

# Train-test split
X_train, X_test, y_train, y_test = train_test_split(features_scaled, target, test_size=0.2, random_state=42)

# Train the model
model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# Save the model and scaler
joblib.dump(model, 'organ_matching_model.pkl')
joblib.dump(scaler, 'scaler.pkl')

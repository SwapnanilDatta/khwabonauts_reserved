from sklearn.preprocessing import LabelEncoder
import joblib

# List of all possible blood types
blood_types = ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"]

# Create and fit the label encoder
label_encoder = LabelEncoder()
label_encoder.fit(blood_types)

# Save the new label encoder
joblib.dump(label_encoder, 'label_encoder.pkl')
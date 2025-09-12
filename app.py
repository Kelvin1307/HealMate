from flask import Flask, render_template, jsonify
import json
import os
from collections import Counter
from datetime import datetime

app = Flask(__name__)

DATA_FOLDER = "users_data"

def load_all_user_data():
    all_data = []
    for file in os.listdir(DATA_FOLDER):
        if file.endswith(".json"):
            with open(os.path.join(DATA_FOLDER, file), "r") as f:
                user_data = json.load(f)
                all_data.append(user_data)
    return all_data

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/symptoms')
def api_symptoms():
    all_data = load_all_user_data()

    # Example: Count symptom mentions
    symptom_counter = Counter()
    for d in all_data:
        symptoms = d.get("symptoms", "")
        for symptom in ["fever", "cough", "headache", "stomach ache", "diarrhea"]:
            if symptom in symptoms.lower():
                symptom_counter[symptom] += 1

    return jsonify(symptom_counter)

if __name__ == '__main__':
    app.run(debug=True)

from pathlib import Path
import math

import joblib
import pandas as pd
from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import BadRequest

app = Flask(__name__)

FEATURE_NAMES = ["Bedrooms", "Bath", "Floor_area (sqm)", "Land_area (sqm)"]
FEATURE_LIMITS = {
    "Bedrooms": (1, 5),
    "Bath": (1, 4),
    "Floor_area (sqm)": (20, 1000),
    "Land_area (sqm)": (20, 30000),
}
INTEGER_FEATURES = {"Bedrooms", "Bath"}
MODEL_PATH = Path(__file__).resolve().parent / "models" / "house_price_xgboost.pkl"

MODEL = joblib.load(MODEL_PATH)

# Sample nearby comparable sales displayed on the frontend
COMPARABLE_SALES = [
    {
        "price": "₱1,265,000",
        "address": "4204 Lost Creek Blvd",
        "beds": "4 Beds",
        "baths": "3 Baths",
        "sqft": "270 sqm",
        "image_alt": "Modern home facade",
        "image": "images/House1.jpg",
    },
    {
        "price": "₱1,230,000",
        "address": "1811 Rollingwood Dr",
        "beds": "4 Beds",
        "baths": "3.5 Baths",
        "sqft": "258 sqm",
        "image_alt": "Contemporary residence",
        "image": "images/House2.jpg",
    },
    {
        "price": "₱1,280,000",
        "address": "904 Skyline Terrace",
        "beds": "5 Beds",
        "baths": "3 Baths",
        "sqft": "276 sqm",
        "image_alt": "Modern luxury home",
        "image": "images/House3.jpg",
    },
]


@app.route("/")
def index():
    """Render the main EstiMate valuation interface."""
    return render_template("index.html", comparables=COMPARABLE_SALES)


@app.route("/predict", methods=["POST"])
def predict():
    """Return a house-price estimate from the trained model."""
    if not request.is_json:
        return jsonify(error="Expected a JSON request body."), 400

    try:
        payload = request.get_json()
    except BadRequest:
        return jsonify(error="Request body must contain valid JSON."), 400

    if not isinstance(payload, dict):
        return jsonify(error="Request body must be a JSON object."), 400

    values = {}
    for feature in FEATURE_NAMES:
        if feature not in payload:
            return jsonify(error=f"Missing required input: {feature}."), 400

        value = payload[feature]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return jsonify(error=f"{feature} must be a number."), 400

        try:
            number = float(value)
        except (OverflowError, ValueError):
            return jsonify(error=f"{feature} must be a finite number."), 400

        if not math.isfinite(number):
            return jsonify(error=f"{feature} must be a finite number."), 400

        minimum, maximum = FEATURE_LIMITS[feature]
        if not minimum <= number <= maximum:
            return jsonify(
                error=f"{feature} must be between {minimum} and {maximum}."
            ), 400

        if feature in INTEGER_FEATURES and not number.is_integer():
            return jsonify(error=f"{feature} must be a whole number."), 400

        values[feature] = number

    input_frame = pd.DataFrame(
        [[values[feature] for feature in FEATURE_NAMES]],
        columns=FEATURE_NAMES,
    )

    try:
        prediction = float(MODEL.predict(input_frame)[0])
        if not math.isfinite(prediction):
            raise ValueError("Model returned a non-finite prediction.")
    except Exception:
        app.logger.exception("House price prediction failed.")
        return jsonify(error="The estimate could not be calculated. Please try again."), 500

    return jsonify(prediction=prediction, currency="PHP")


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)

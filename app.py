from pathlib import Path
import json
import math
import re

import joblib
import numpy as np
import pandas as pd
from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import BadRequest

import house_features  # noqa: F401  (the saved pipeline imports this module)

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "models"
RESULTS_DIR = BASE_DIR / "results"
SETTINGS_PATH = BASE_DIR / "settings.txt"
MODEL_PATH = MODELS_DIR / "house_price_xgboost.pkl"

MODEL = joblib.load(MODEL_PATH)
ALL_MODELS = joblib.load(MODELS_DIR / "all_models.pkl")
MODEL_INFO = json.loads((MODELS_DIR / "model_info.json").read_text(encoding="utf-8"))
LISTINGS = json.loads((MODELS_DIR / "listings.json").read_text(encoding="utf-8"))

PROPERTY_TYPE = "Property_Type"
BATH = "Bath"
LAND = "Land_area (sqm)"
FLOOR = "Floor_area (sqm)"
BEDROOMS = "Bedrooms"
FEATURE_NAMES = MODEL_INFO["features"]
INTEGER_FEATURES = {BEDROOMS, BATH}

# Inputs each property type accepts, with limits from the training data.
# Condos in the dataset almost never list land area, and houses almost never
# list baths, so the model only sees the fields it was trained on for that type.
FEATURE_LIMITS = MODEL_INFO["limits"]
RANGE_LOW, RANGE_HIGH = MODEL_INFO["range_ratio"]
MARKET_BASELINE = MODEL_INFO["market_baseline"]

# --- Market assumptions for the stat cards ---------------------------------
# Gross rental yield: Global Property Guide, Philippines average, Q1 2026.
GROSS_RENTAL_YIELD = 0.0511
# Residential Real Estate Price Index year-on-year change: BSP, Q2 2026.
MARKET_TREND = {
    "percent": 0.4,
    "source": "BSP Residential Real Estate Price Index, Q2 2026 (year-on-year)",
}

COMPARABLE_COUNT = 3

DEFAULT_SETTINGS = {
    "showlistings": True,
    "showdifferentmodels": True,
    "showstatistics": True,
}


def load_settings():
    """Read settings.txt on each request, so edits apply after a page refresh."""
    settings = dict(DEFAULT_SETTINGS)
    try:
        text = SETTINGS_PATH.read_text(encoding="utf-8")
    except OSError:
        app.logger.warning("settings.txt not found; showing every section.")
        return settings

    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        match = re.fullmatch(r"(\w+)\s*=\s*([01])", line)
        if match and match[1].lower() in settings:
            settings[match[1].lower()] = match[2] == "1"
        else:
            app.logger.warning("Ignoring invalid line in settings.txt: %s", line)
    return settings


def _format_peso(value):
    return f"₱{value:,.0f}"


def _format_r2(value):
    return f"{value:.3f}"


def build_statistics():
    """Compare every tuned model on cross-validation and test performance."""
    tuned = pd.read_csv(RESULTS_DIR / "tuned_model_comparison.csv").set_index("Model")
    final = pd.read_csv(RESULTS_DIR / "final_model_comparison.csv").set_index("Model")
    metrics = [
        ("CV MAE", tuned["MAE (PHP)"], _format_peso, False),
        ("CV R²", tuned["R2 Score"], _format_r2, True),
        ("Test MAE", final["MAE (PHP)"], _format_peso, False),
        ("Test RMSE", final["RMSE (PHP)"], _format_peso, False),
        ("Test R²", final["R2 Score"], _format_r2, True),
    ]
    rows = []
    for name in tuned.index:
        cells = []
        for _, series, formatter, higher_is_better in metrics:
            best = series.max() if higher_is_better else series.min()
            is_best = series[name] == best
            gap = abs(series[name] - best)
            cells.append({
                "value": formatter(series[name]),
                "is_best": bool(is_best),
                "gap": None if is_best else ("-" if higher_is_better else "+") + formatter(gap),
            })
        rows.append({
            "name": name,
            "selected": name == MODEL_INFO["model_name"],
            "cells": cells,
        })
    return {"columns": [metric[0] for metric in metrics], "rows": rows}


def find_comparables(property_type, values):
    """Return the most similar real listings of the same property type."""

    def distance(listing):
        score = abs(math.log(listing[FLOOR] / values[FLOOR]))
        score += 0.25 * abs(listing[BEDROOMS] - values[BEDROOMS])
        if LAND in values:
            score += abs(math.log(listing[LAND] / values[LAND]))
        return score

    candidates = [
        listing for listing in LISTINGS
        if listing[PROPERTY_TYPE] == property_type
        and listing[FLOOR] and listing[BEDROOMS]
        and (LAND not in values or listing[LAND])
    ]
    return [
        {
            "price": listing["Price (PHP)"],
            "title": listing["Description"],
            "location": listing["Location"],
            "beds": listing[BEDROOMS],
            "baths": listing[BATH],
            "floor_area": listing[FLOOR],
            "land_area": listing[LAND],
            "link": listing["Link"],
        }
        for listing in sorted(candidates, key=distance)[:COMPARABLE_COUNT]
    ]


def predict_price(property_type, values, model=None):
    """Return a model's estimate; fields a type doesn't use stay missing."""
    row = {**{feature: np.nan for feature in FEATURE_NAMES}, **values,
           PROPERTY_TYPE: property_type}
    frame = pd.DataFrame([row], columns=FEATURE_NAMES)
    numeric = [feature for feature in FEATURE_NAMES if feature != PROPERTY_TYPE]
    frame[numeric] = frame[numeric].astype("float64")
    price = float((MODEL if model is None else model).predict(frame)[0])
    if not math.isfinite(price) or price <= 0:
        raise ValueError(f"Model returned an invalid estimate: {price!r}")
    return price


@app.route("/")
def index():
    """Render the main EstiMate valuation interface."""
    settings = load_settings()
    return render_template(
        "index.html",
        market_trend=MARKET_TREND,
        limits=FEATURE_LIMITS,
        settings=settings,
        statistics=build_statistics() if settings["showstatistics"] else None,
    )


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

    property_type = payload.get(PROPERTY_TYPE)
    if property_type is None:
        return jsonify(error=f"Missing required input: {PROPERTY_TYPE}."), 400
    if not isinstance(property_type, str) or property_type not in FEATURE_LIMITS:
        options = ", ".join(FEATURE_LIMITS)
        return jsonify(error=f"{PROPERTY_TYPE} must be one of: {options}."), 400

    values = {}
    for feature, (minimum, maximum) in FEATURE_LIMITS[property_type].items():
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

        if not minimum <= number <= maximum:
            return jsonify(
                error=f"{feature} must be between {minimum} and {maximum}."
            ), 400

        if feature in INTEGER_FEATURES and not number.is_integer():
            return jsonify(error=f"{feature} must be a whole number."), 400

        values[feature] = number

    try:
        prediction = predict_price(property_type, values)
        settings = load_settings()
        model_estimates = []
        if settings["showdifferentmodels"]:
            for name, model in ALL_MODELS.items():
                selected = name == MODEL_INFO["model_name"]
                estimate = prediction if selected else predict_price(property_type, values, model)
                model_estimates.append(
                    {"name": name, "estimate": estimate, "selected": selected}
                )
    except Exception:
        app.logger.exception("House price prediction failed.")
        return jsonify(error="The estimate could not be calculated. Please try again."), 500

    return jsonify(
        prediction=prediction,
        model_name=MODEL_INFO["model_name"],
        model_estimates=model_estimates,
        currency="PHP",
        estimated_range=[prediction * RANGE_LOW, prediction * RANGE_HIGH],
        market_baseline=MARKET_BASELINE[property_type],
        price_per_sqm=prediction / values[FLOOR],
        monthly_rent=prediction * GROSS_RENTAL_YIELD / 12,
        market_trend=MARKET_TREND,
        comparables=(
            find_comparables(property_type, values) if settings["showlistings"] else []
        ),
    )


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)

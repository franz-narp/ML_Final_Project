# EstiMate: Philippine Property Price Prediction

EstiMate estimates the asking price of a Philippine condo or house. It uses a tuned XGBoost regression model trained on real Lamudi listings and served with Flask.

## Project contents

| Path | Purpose |
|---|---|
| `notebooks/House_Price_Prediction.ipynb` | Full workflow: cleaning, analysis, features, tuning, evaluation, export |
| `data/PH_houses_v2.csv` | Source dataset (1,500 listings) |
| `house_features.py` | Feature engineering used by both the notebook and the app |
| `models/` | Trained pipeline, its metadata, and listings for the comparison cards |
| `results/` | Baseline, tuned and final model comparison tables |
| `app.py`, `templates/`, `static/` | Flask web application |
| `tests/` | Automated API tests |

## Run the application

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Open `http://127.0.0.1:5000`.

To re-run the notebook, also install `matplotlib`, `seaborn` and `jupyter`.

## Display settings

Edit `settings.txt`, save, and refresh the page. Use `1` for on and `0` for off.

| Setting | When 1 | When 0 |
|---|---|---|
| `showlistings` | Shows similar real listings | Hides them |
| `showdifferentmodels` | Shows all four models' estimates side by side | Shows only the best model (constrained XGBoost) |
| `showstatistics` | Shows the table comparing model performance | Hides it |

## Model

1,196 residential listings remain after cleaning. Inputs are property type, bedrooms, floor area, and bath count (condos) or land area (houses). Condos in the data almost never list land, and houses almost never list baths, so each type only uses the fields that exist for it. The app limits inputs to the ranges seen in training.

| Model | CV MAE (PHP) | Test MAE (PHP) | Test R2 |
|---|---|---|---|
| **XGBoost (constrained, selected)** | 1,549,719 | 1,470,855 | 0.950 |
| XGBoost | 1,598,523 | 1,446,345 | 0.953 |
| Random Forest | 1,756,978 | 1,716,364 | 0.916 |
| Multiple Linear Regression | 2,840,097 | 2,888,199 | 0.817 |

The model predicts log price, so estimates are always positive. Monotonic constraints stop larger homes or extra baths from directly lowering the price.

## API

`POST /predict` takes JSON with `Property_Type` (`Condo / Apartment` or `House / Townhouse`), `Bedrooms` and `Floor_area (sqm)`, plus `Bath` for condos or `Land_area (sqm)` for houses.

The response includes `prediction`, `model_name`, `model_estimates`, `estimated_range`, `market_baseline`, `price_per_sqm`, `monthly_rent`, `market_trend` and `comparables`.

- **Estimated range**: 10th to 90th percentile of cross-validated actual-to-predicted price ratios.
- **Market baseline**: middle 50% of listed prices for the property type.
- **Est. rent**: estimate x 5.11% gross yield / 12 (Global Property Guide, Q1 2026, apartment-based).
- **Market trend**: BSP Residential Real Estate Price Index, Q2 2026 year-on-year.

## Limitations

Prices are asking prices, not sales. Location is not a model input. Listings have no dates, so the model cannot show trends over time. Bedrooms are not constrained: for a given floor area, more bedrooms can lower the estimate, as more bedrooms means smaller rooms in this data.

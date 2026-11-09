"""Feature engineering shared by the training notebook and the Flask app.

The saved pipeline references this function by name, so it must stay importable
wherever the model is loaded.
"""
import numpy as np


def create_property_features(X):
    """Add log floor area and floor area per bedroom to a feature frame."""
    X = X.copy()
    X["Log_Floor_Area"] = np.log1p(X["Floor_area (sqm)"].clip(lower=0))
    X["Floor_Area_Per_Bedroom"] = (
        X["Floor_area (sqm)"] / X["Bedrooms"].replace(0, np.nan)
    )
    return X

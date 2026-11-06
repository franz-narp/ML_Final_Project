import math
import unittest
from unittest.mock import patch

from app import FEATURE_NAMES, MODEL, MODEL_PATH, app


VALID_INPUT = {
    "Bedrooms": 4,
    "Bath": 3,
    "Floor_area (sqm)": 250,
    "Land_area (sqm)": 300,
}


class PredictionEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def test_model_generates_finite_numeric_prediction(self):
        import pandas as pd

        self.assertTrue(MODEL_PATH.is_file())
        self.assertTrue(MODEL_PATH.with_name("model_info.json").is_file())
        prediction = MODEL.predict(
            pd.DataFrame([[4, 3, 250, 300]], columns=FEATURE_NAMES)
        )[0]
        self.assertIsInstance(prediction.item(), (int, float))
        self.assertTrue(math.isfinite(float(prediction)))

    def test_homepage_loads(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"EstiMate", response.data)
        self.assertIn(b"Recent Nearby Sales", response.data)

    def test_prediction_returns_json(self):
        response = self.client.post("/predict", json=VALID_INPUT)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["currency"], "PHP")
        self.assertIsInstance(response.json["prediction"], (int, float))
        self.assertTrue(math.isfinite(response.json["prediction"]))

    def test_model_error_returns_json_server_error(self):
        with patch("app.MODEL.predict", side_effect=RuntimeError("test failure")):
            response = self.client.post("/predict", json=VALID_INPUT)
        self.assertEqual(response.status_code, 500)
        self.assertIn("could not be calculated", response.json["error"])

    def test_missing_input_is_rejected(self):
        data = VALID_INPUT.copy()
        del data["Bath"]
        response = self.client.post("/predict", json=data)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Missing required input", response.json["error"])

    def test_non_numeric_input_is_rejected(self):
        data = VALID_INPUT.copy()
        data["Bedrooms"] = "four"
        response = self.client.post("/predict", json=data)
        self.assertEqual(response.status_code, 400)

    def test_negative_input_is_rejected(self):
        data = VALID_INPUT.copy()
        data["Bedrooms"] = -1
        response = self.client.post("/predict", json=data)
        self.assertEqual(response.status_code, 400)

    def test_non_finite_inputs_are_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                data = VALID_INPUT.copy()
                data["Floor_area (sqm)"] = value
                response = self.client.post("/predict", json=data)
                self.assertEqual(response.status_code, 400)

    def test_excessively_large_input_is_rejected(self):
        data = VALID_INPUT.copy()
        data["Land_area (sqm)"] = 30001
        response = self.client.post("/predict", json=data)
        self.assertEqual(response.status_code, 400)

    def test_non_json_request_is_rejected(self):
        response = self.client.post("/predict", data="not json")
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()

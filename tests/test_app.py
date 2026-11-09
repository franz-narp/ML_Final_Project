import math
import unittest
from unittest.mock import patch

import tempfile
from pathlib import Path

import app as app_module
from app import MODEL_PATH, app, predict_price

CONDO = "Condo / Apartment"
HOUSE = "House / Townhouse"
VALID_INPUT = {
    "Property_Type": CONDO,
    "Bedrooms": 2,
    "Bath": 2,
    "Floor_area (sqm)": 70,
}
VALID_HOUSE = {
    "Property_Type": HOUSE,
    "Bedrooms": 3,
    "Floor_area (sqm)": 100,
    "Land_area (sqm)": 120,
}


class PredictionEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def setUp(self):
        patcher = patch("app.load_settings", return_value=self.settings())
        patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def settings(**changes):
        return {**app_module.DEFAULT_SETTINGS, **changes}

    def set_settings(self, **changes):
        app_module.load_settings.return_value = self.settings(**changes)

    def test_listings_setting(self):
        self.set_settings(showlistings=False)
        self.assertNotIn(b"Similar Listings", self.client.get("/").data)
        self.assertEqual(self.client.post("/predict", json=VALID_INPUT).json["comparables"], [])

    def test_different_models_setting(self):
        response = self.client.post("/predict", json=VALID_INPUT).json
        self.assertEqual(len(response["model_estimates"]), 4)
        selected = [m for m in response["model_estimates"] if m["selected"]]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["estimate"], response["prediction"])
        self.assertTrue(all(m["estimate"] > 0 for m in response["model_estimates"]))

        self.set_settings(showdifferentmodels=False)
        self.assertNotIn(b"What Each Model Estimates", self.client.get("/").data)
        off = self.client.post("/predict", json=VALID_INPUT).json
        self.assertEqual(off["model_estimates"], [])
        self.assertEqual(off["prediction"], response["prediction"])

    def test_statistics_setting(self):
        page = self.client.get("/").data.decode("utf-8")
        self.assertIn("Model Performance", page)
        self.assertIn("Random Forest Regressor", page)
        self.set_settings(showstatistics=False)
        self.assertNotIn(b"Model Performance", self.client.get("/").data)

    def test_model_files_exist(self):
        self.assertTrue(MODEL_PATH.is_file())
        self.assertTrue(MODEL_PATH.with_name("model_info.json").is_file())

    def test_homepage_loads(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"EstiMate", response.data)
        self.assertIn(b"Similar Listings", response.data)
        self.assertNotIn(b"Lost Creek", response.data)

    def test_condo_and_house_predictions_return_all_fields(self):
        for body in (VALID_INPUT, VALID_HOUSE):
            with self.subTest(body=body):
                response = self.client.post("/predict", json=body)
                self.assertEqual(response.status_code, 200)
                data = response.json
                self.assertEqual(data["currency"], "PHP")
                self.assertTrue(math.isfinite(data["prediction"]))
                low, high = data["estimated_range"]
                self.assertLess(low, data["prediction"])
                self.assertGreater(high, data["prediction"])
                self.assertEqual(len(data["comparables"]), 3)
                self.assertTrue(data["comparables"][0]["link"].startswith("https://"))

    def test_predictions_are_positive_at_every_smallest_input(self):
        rows = [
            (CONDO, {"Bedrooms": b, "Bath": ba, "Floor_area (sqm)": 17})
            for b in range(1, 5) for ba in range(1, 4)
        ] + [
            (HOUSE, {"Bedrooms": b, "Floor_area (sqm)": 25, "Land_area (sqm)": 36})
            for b in range(1, 6)
        ]
        for property_type, values in rows:
            with self.subTest(property_type=property_type, values=values):
                self.assertGreater(predict_price(property_type, values), 0)

    def test_price_rises_with_floor_area_at_fixed_bedrooms(self):
        previous = 0
        for floor in (20, 40, 70, 120, 200, 400):
            price = predict_price(CONDO, {"Bedrooms": 2, "Bath": 2, "Floor_area (sqm)": floor})
            self.assertGreater(price, previous)
            previous = price

    def test_more_baths_never_lowers_a_condo_price(self):
        prices = [
            predict_price(CONDO, {"Bedrooms": 2, "Bath": b, "Floor_area (sqm)": 70})
            for b in (1, 2, 3)
        ]
        self.assertEqual(prices, sorted(prices))

    def test_four_baths_is_rejected(self):
        response = self.client.post("/predict", json={**VALID_INPUT, "Bath": 4})
        self.assertEqual(response.status_code, 400)

    def test_condo_requires_bath_and_house_requires_land(self):
        condo = {k: v for k, v in VALID_INPUT.items() if k != "Bath"}
        house = {k: v for k, v in VALID_HOUSE.items() if k != "Land_area (sqm)"}
        for body in (condo, house):
            response = self.client.post("/predict", json=body)
            self.assertEqual(response.status_code, 400)
            self.assertIn("Missing required input", response.json["error"])

    def test_unknown_property_type_is_rejected(self):
        response = self.client.post("/predict", json={**VALID_INPUT, "Property_Type": "Castle"})
        self.assertEqual(response.status_code, 400)

    def test_model_error_returns_json_server_error(self):
        with patch("app.MODEL.predict", side_effect=RuntimeError("test failure")):
            response = self.client.post("/predict", json=VALID_INPUT)
        self.assertEqual(response.status_code, 500)
        self.assertIn("could not be calculated", response.json["error"])

    def test_non_numeric_input_is_rejected(self):
        response = self.client.post("/predict", json={**VALID_INPUT, "Bedrooms": "four"})
        self.assertEqual(response.status_code, 400)

    def test_out_of_range_inputs_are_rejected(self):
        for change in ({"Bedrooms": -1}, {"Floor_area (sqm)": 5000}):
            response = self.client.post("/predict", json={**VALID_INPUT, **change})
            self.assertEqual(response.status_code, 400)

    def test_non_finite_inputs_are_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                response = self.client.post("/predict", json={**VALID_INPUT, "Floor_area (sqm)": value})
                self.assertEqual(response.status_code, 400)

    def test_non_json_request_is_rejected(self):
        response = self.client.post("/predict", data="not json")
        self.assertEqual(response.status_code, 400)


class SettingsFileTests(unittest.TestCase):
    def load(self, text):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.txt"
            path.write_text(text, encoding="utf-8")
            with patch("app.SETTINGS_PATH", path):
                return app_module.load_settings()

    def test_reads_values_comments_and_spacing(self):
        result = self.load("# note\nshowlistings=0\n showStatistics = 0  # off\nshowdifferentmodels = 1\n")
        self.assertFalse(result["showlistings"])
        self.assertFalse(result["showstatistics"])
        self.assertTrue(result["showdifferentmodels"])

    def test_invalid_values_keep_defaults(self):
        result = self.load("showlistings = maybe\nunknown = 0\n")
        self.assertEqual(result, app_module.DEFAULT_SETTINGS)

    def test_missing_file_uses_defaults(self):
        with patch("app.SETTINGS_PATH", Path("does-not-exist.txt")):
            self.assertEqual(app_module.load_settings(), app_module.DEFAULT_SETTINGS)


if __name__ == "__main__":
    unittest.main()

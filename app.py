from flask import Flask, render_template

app = Flask(__name__)

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


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)

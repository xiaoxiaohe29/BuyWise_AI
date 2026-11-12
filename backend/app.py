
from fastapi import FastAPI
from pydantic import BaseModel, Field
from pathlib import Path
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import joblib
import re
import html

# Create FastAPI application
app = FastAPI(title="BuyWise AI API")
sentiment_analyzer = SentimentIntensityAnalyzer()

# Locate saved model
BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "models" / "fake_review_model.joblib"

# Load trained model
model = joblib.load(MODEL_PATH)


# Input format
class ReviewInput(BaseModel):
    review_text: str = Field(min_length=1, max_length=20000)



# Text cleaning
def clean_text(text):
    return text

# Homepage
@app.get("/")
def home():
    return {
        "message": "Welcome to BuyWise AI!",
        "status": "running"
    }


# Review analysis
@app.post("/analyze-review")
def analyze_review(review: ReviewInput):

    cleaned = clean_text(review.review_text)

    if not cleaned:
        return {
            "status": "insufficient_text",
            "message": "No usable review text was provided."
        }

    # Part 1: Fake Review Detection (existing ML model)
    prediction = int(model.predict([cleaned])[0])

    score = float(
        model.predict_proba([cleaned])[0][1]
    )

    if prediction == 1:
        result = "Potentially suspicious text pattern"
    else:
        result = "No suspicious pattern detected by this model"

    # Part 2: Sentiment Analysis (VADER)
    # Use original review text to preserve punctuation and emphasis
    sentiment_scores = sentiment_analyzer.polarity_scores(
        review.review_text
    )

    compound = sentiment_scores["compound"]

    if compound >= 0.05:
        sentiment = "Positive"
    elif compound <= -0.05:
        sentiment = "Negative"
    else:
        sentiment = "Neutral"

    return {
        "review_text": review.review_text,
        "prediction": prediction,
        "model_score": round(score, 4),
        "result": result,
        "sentiment": sentiment,
        "sentiment_score": round(compound, 4),
        "disclaimer": (
            "This is a research-based text screening result, "
            "not proof that a review is fake."
        )
    }



# -------------------------------------
# Seller Trust Assessment API
# -------------------------------------

from seller_trust import assess_seller


class SellerInput(BaseModel):
    rating: float = Field(ge=0, le=5)
    total_reviews: int = Field(ge=0)
    return_policy_available: bool
    verified_seller: bool


@app.post("/analyze-seller")
def analyze_seller(seller: SellerInput):

    result = assess_seller(
        rating=seller.rating,
        total_reviews=seller.total_reviews,
        return_policy_available=seller.return_policy_available,
        verified_seller=seller.verified_seller
    )

    return result


# -------------------------------------
# Return & Refund Intelligence API
# -------------------------------------

from return_analysis import analyze_return


class ReturnInput(BaseModel):
    reason: str = Field(min_length=1, max_length=5000)


@app.post("/analyze-return")
def analyze_return_endpoint(data: ReturnInput):
    return analyze_return(data.reason)


# -------------------------------------
# BuyWise AI Product Intelligence Report
# -------------------------------------

class ProductReportInput(BaseModel):
    product_name: str = Field(min_length=1, max_length=200)
    review_text: str = Field(min_length=1, max_length=20000)
    seller: SellerInput
    return_reasons: list[str] = Field(default_factory=list, max_length=100)


@app.post("/product-report")
def product_report(data: ProductReportInput):

    # 1. Review pattern analysis
    review_result = analyze_review(
        ReviewInput(review_text=data.review_text)
    )

    # 2. Seller evidence assessment
    seller_result = analyze_seller(data.seller)

    # 3. Return feedback analysis
    return_results = [
        analyze_return(reason)
        for reason in data.return_reasons
    ]

    # 4. Combine all results
    return {
        "product_name": data.product_name,
        "review_analysis": review_result,
        "seller_assessment": seller_result,
        "return_analysis": return_results,
        "disclaimer": (
            "This report uses preliminary research and "
            "rule-based indicators. It does not verify "
            "seller safety or review authenticity."
        )
    }


# -------------------------------------
# BuyWise AI Frontend
# -------------------------------------

from fastapi.responses import FileResponse


@app.get("/dashboard", include_in_schema=False)
def dashboard():
    return FileResponse(BASE_DIR / "frontend" / "index.html")


# ==========================================
# Smart Shopping Integration
# ==========================================

from shopping.main import app as shopping_app

app.mount("/shopping", shopping_app)


# Seller Credibility React Application

SELLER_DIST = (
    Path(__file__).resolve().parent.parent
    / "seller_credibility"
    / "ProcureMeta-AI-New"
    / "dist"
)

app.mount(
    "/seller-credibility/assets",
    StaticFiles(directory=SELLER_DIST / "assets"),
    name="seller-assets"
)

@app.get("/seller-credibility/")
def seller_credibility_page():
    return FileResponse(SELLER_DIST / "index.html")

@app.get("/coupon-bundle/")
def coupon_bundle_page():
    return FileResponse(SELLER_DIST / "index.html")



# -------------------------------------
# Coupon Advisor - Product URL Recognition
# -------------------------------------

from urllib.parse import urlparse
from fastapi import HTTPException

class ProductPreviewInput(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


@app.post("/api/product-preview")
def product_preview(data: ProductPreviewInput):
    parsed = urlparse(data.url.strip())

    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=400,
            detail="Enter a valid HTTP or HTTPS URL."
        )

    if parsed.username or parsed.password or parsed.port is not None:
        raise HTTPException(
            status_code=400,
            detail="Invalid shopping URL."
        )

    hostname = (parsed.hostname or "").lower().rstrip(".")

    marketplaces = {
        "amazon.com": "amazon",
        "amazon.com.my": "amazon",
        "amazon.sg": "amazon",
        "amazon.co.uk": "amazon",
        "ebay.com": "ebay",
        "ebay.co.uk": "ebay",
        "shopee.com.my": "shopee",
        "shopee.sg": "shopee",
        "lazada.com.my": "lazada",
        "lazada.sg": "lazada",
    }

    platform = next(
        (
            name for domain, name in marketplaces.items()
            if hostname == domain
            or hostname.endswith("." + domain)
        ),
        None
    )

    if platform is None:
        raise HTTPException(
            status_code=400,
            detail="This marketplace is not supported yet."
        )

    # Extract product identifier when available.
    product_id = None

    if platform == "amazon":
        match = re.search(
            r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:/|$)",
            parsed.path,
            re.IGNORECASE
        )
        if match:
            product_id = match.group(1).upper()

    elif platform == "ebay":
        match = re.search(
            r"/itm/(?:[^/]+/)?(\d{9,15})(?:/|$)",
            parsed.path
        )
        if match:
            product_id = match.group(1)

    return {
        "recognized": True,
        "platform": platform,
        "product_id": product_id,
        "url": parsed.geturl(),
        "requires_manual_confirmation": True,
        "currency": "USD",
        "message": (
            f"{platform.title()} URL recognized. "
            "Please enter the product name and USD price."
        )
    }



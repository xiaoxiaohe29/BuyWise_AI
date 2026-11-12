# BuyWise AI

BuyWise AI is a prototype shopping intelligence assistant.

## Features

- Review text pattern analysis using machine learning
- Seller evidence assessment
- Return reason classification
- Combined Product Intelligence Report
- Web dashboard powered by FastAPI

## Technology

- Python
- FastAPI
- Scikit-learn
- HTML, CSS and JavaScript

## Setup

Use a compatible Python environment (Python 3.12 recommended).

Install dependencies:

    python -m pip install -r requirements.txt

Start the backend from the project root:

    python -m uvicorn backend.app:app --reload

Open the dashboard:

    http://127.0.0.1:8000/dashboard

## Important limitations

Review classification uses research-derived proxy labels,
not independently verified fake-review labels.

Seller evidence scores use illustrative rules, not validated
trust or fraud-risk estimates.

Return reason classification uses keyword matching.

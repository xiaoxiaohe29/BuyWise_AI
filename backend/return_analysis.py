
import re

RETURN_KEYWORDS = {
    "Defective product": [
        "broken", "defective", "damaged",
        "not working", "stopped working",
        "faulty", "doesn't work"
    ],
    "Not as described": [
        "not as described", "different from picture",
        "wrong size", "wrong color",
        "misleading", "not as advertised"
    ],
    "Delivery issues": [
        "late delivery", "delayed",
        "never arrived", "lost package",
        "wrong item delivered"
    ],
    "Changed mind": [
        "changed my mind", "no longer needed",
        "ordered by mistake",
        "don't want it anymore"
    ]
}


def analyze_return(reason):
    text = reason.lower()

    matched_categories = []

    for category, keywords in RETURN_KEYWORDS.items():
        for keyword in keywords:
            pattern = r"(?<!\\w)" + re.escape(keyword) + r"(?!\\w)"

            if re.search(pattern, text):
                matched_categories.append(category)
                break

    if not matched_categories:
        return {
            "category": "Other / Unknown",
            "matched_categories": [],
            "status": "no_keyword_match"
        }

    return {
        "category": matched_categories[0],
        "matched_categories": matched_categories,
        "status": (
            "multiple_matches"
            if len(matched_categories) > 1
            else "keyword_match"
        )
    }

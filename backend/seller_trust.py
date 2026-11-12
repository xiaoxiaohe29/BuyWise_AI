
def assess_seller(
    rating,
    total_reviews,
    return_policy_available,
    verified_seller
):
    score = 0
    observations = []

    if rating >= 4.5:
        score += 30
    elif rating >= 4.0:
        score += 20
    elif rating >= 3.0:
        score += 10
    else:
        observations.append("Low seller rating")

    if total_reviews >= 100:
        score += 25
    elif total_reviews >= 20:
        score += 15
    elif total_reviews > 0:
        score += 5
    else:
        observations.append("No customer reviews available")

    if return_policy_available:
        score += 25
    else:
        observations.append("Return policy information unavailable")

    if verified_seller:
        score += 20
    else:
        observations.append("Seller verification not confirmed")

    return {
        "evidence_score": score,
        "observations": observations,
        "disclaimer": (
            "This is a preliminary rule-based evidence score, "
            "not a verified measure of seller trustworthiness."
        )
    }

from app.services.seo_opportunities import detect_opportunities, OpportunityThresholds

def test_low_ctr_and_position_boundaries():
    rows = detect_opportunities({"impressions": 100, "ctr": .019, "position": 4}, target="brand", period="28d")
    assert {row["rule_type"] for row in rows} == {"LOW_CTR", "RANKING_OPPORTUNITY"}

def test_click_decline_requires_previous_volume_and_uses_boundary():
    rows = detect_opportunities({"clicks": 70}, {"clicks": 100})
    assert any(row["rule_type"] == "CLICK_DECLINE" for row in rows)
    assert not detect_opportunities({"clicks": 0}, {"clicks": 0})

def test_missing_metrics_are_safe():
    assert detect_opportunities({}, {}) == []

def test_ranking_decline_is_explainable():
    rows = detect_opportunities({"position": 8}, {"position": 4})
    assert rows[0]["rule_type"] == "RANKING_DECLINE"

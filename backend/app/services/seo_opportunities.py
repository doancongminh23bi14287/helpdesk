"""Deterministic, explainable SEO signals. No provider or database access."""
from dataclasses import dataclass
from typing import Any, Mapping

@dataclass(frozen=True)
class OpportunityThresholds:
    min_impressions: int = 100
    low_ctr: float = 0.02
    position_min: float = 4.0
    position_max: float = 10.0
    click_decline_percent: float = 30.0
    position_decline: float = 3.0

def _num(value: Any) -> float | None:
    try:
        result = float(value)
        return result if result == result else None
    except (TypeError, ValueError):
        return None

def detect_opportunities(current: Mapping[str, Any], previous: Mapping[str, Any] | None = None, thresholds: OpportunityThresholds | None = None, target: str | None = None, period: str | None = None) -> list[dict[str, Any]]:
    t = thresholds or OpportunityThresholds()
    impressions, clicks = _num(current.get("impressions")), _num(current.get("clicks"))
    ctr, position = _num(current.get("ctr")), _num(current.get("position", current.get("average_position")))
    prev_clicks = _num((previous or {}).get("clicks"))
    prev_position = _num((previous or {}).get("position", (previous or {}).get("average_position")))
    out = []
    def add(rule, evidence, action, threshold):
        out.append({"rule_type": rule, "target": target, "period": period, "current": dict(current), "previous": dict(previous) if previous else None, "threshold": threshold, "evidence": evidence, "explanation": evidence, "recommended_action": action})
    if impressions is not None and impressions >= t.min_impressions and ctr is not None and ctr < t.low_ctr:
        add("LOW_CTR", f"CTR {ctr:.2%} is below {t.low_ctr:.2%} with {impressions:.0f} impressions.", "Review title and meta description", t.low_ctr)
    if impressions is not None and impressions >= t.min_impressions and position is not None and t.position_min <= position <= t.position_max:
        add("RANKING_OPPORTUNITY", f"Average position {position:.1f} is within {t.position_min:.1f}-{t.position_max:.1f}.", "Review on-page optimisation", [t.position_min, t.position_max])
    if prev_clicks is not None and prev_clicks >= t.min_impressions and clicks is not None and ((prev_clicks - clicks) / prev_clicks) * 100 >= t.click_decline_percent:
        add("CLICK_DECLINE", f"Clicks declined {((prev_clicks - clicks) / prev_clicks) * 100:.1f}% versus the previous period.", "Review search demand and landing-page changes", t.click_decline_percent)
    if prev_position is not None and position is not None and position - prev_position >= t.position_decline:
        add("RANKING_DECLINE", f"Average position worsened by {position - prev_position:.1f} positions.", "Review technical and content changes", t.position_decline)
    return out

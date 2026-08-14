"""Tests der Gesamtrisiko-Aggregation.

Hintergrund: Der Gesamtscore war ein Mittelwert ueber alle 13 Kategorien.
Bei Wetter 100 und Waldbrand 100 — beide am Anschlag — kam ein Gesamtwert
von 38 heraus ("Erhoeht"), weil elf ruhige Kategorien das Mittel druecken.
Fuer ein Fruehwarnsystem ist das die falsche Rechenart: massgeblich ist das
schlimmste Einzelrisiko, nicht der Durchschnitt.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.alert.alert_engine import (
    BREADTH_THRESHOLD, MIN_RELEVANCE, _relevance, aggregate_overall_score,
)

# Die Gewichte aus calculate_risk_scores
WEIGHTS = {
    "official_warning": 2.0, "water": 1.5, "weather": 1.2, "fire": 1.0,
    "radiation": 1.0, "traffic": 0.8, "seismic": 0.8, "power": 0.7,
    "news": 0.6, "air_quality": 0.5, "health": 0.5, "events": 0.4,
    "shipping": 0.3,
}


def _cats(**scores):
    """Baut den Eingabewert; nicht genannte Kategorien stehen auf 0."""
    return {
        name: {"score": scores.get(name, 0), "weight": weight}
        for name, weight in WEIGHTS.items()
    }


def test_real_situation_is_not_diluted_to_erhoeht():
    """Der gemeldete Fall: zwei Kategorien auf 100 ergaben Gesamtscore 38."""
    result = aggregate_overall_score(_cats(
        weather=100, fire=100, health=70, news=69, water=66, shipping=40,
        official_warning=20,
    ))
    alt_mittelwert = (100 + 100 + 70 + 69 + 66 + 40 + 20) / 13
    assert round(alt_mittelwert) == 36, "Referenz: so rechnete es vorher"
    assert result["score"] >= 80, (
        f"Zwei Kategorien am Anschlag muessen eine ernste Gesamtlage ergeben, "
        f"waren {result['score']}"
    )


def test_single_maxed_category_dominates():
    """Eine Kategorie auf 100 darf nicht von Ruhe ringsum weggemittelt werden."""
    result = aggregate_overall_score(_cats(water=100))
    assert result["score"] >= 85
    assert result["driver"] == "water"


def test_quiet_situation_stays_low():
    result = aggregate_overall_score(_cats(water=15, weather=10, news=5))
    assert result["score"] < 20


def test_all_zero_is_zero():
    assert aggregate_overall_score(_cats())["score"] == 0.0


def test_empty_input_is_safe():
    result = aggregate_overall_score({})
    assert result["score"] == 0.0
    assert result["driver"] is None


def test_concurrent_situations_raise_the_score():
    """Mehrere gleichzeitige Lagen sind schlimmer als eine einzelne."""
    single = aggregate_overall_score(_cats(water=60))
    multi = aggregate_overall_score(_cats(water=60, fire=60, weather=60, traffic=60))
    assert multi["score"] > single["score"]


def test_low_weight_category_has_reduced_but_real_influence():
    """Schifffahrt am Anschlag ist nicht belanglos, aber weniger dringlich."""
    shipping = aggregate_overall_score(_cats(shipping=100))["score"]
    warning = aggregate_overall_score(_cats(official_warning=100))["score"]
    assert shipping < warning, "Hohes Gewicht muss staerker durchschlagen"
    assert shipping >= 100 * MIN_RELEVANCE, "Aber nicht wegdividiert werden"


def test_highest_weighted_category_is_the_driver():
    result = aggregate_overall_score(_cats(shipping=100, official_warning=90))
    # 100 * 0.66 = 66 gegen 90 * 1.0 = 90 -> Behoerdenwarnung bestimmt die Lage
    assert result["driver"] == "official_warning"


def test_score_never_exceeds_100():
    result = aggregate_overall_score({
        name: {"score": 100, "weight": w} for name, w in WEIGHTS.items()
    })
    assert result["score"] <= 100.0


def test_relevance_stays_within_bounds():
    for w in (0.1, 0.3, 1.0, 2.0, 5.0):
        assert MIN_RELEVANCE <= _relevance(w) <= 1.0


def test_concurrent_list_only_counts_elevated():
    result = aggregate_overall_score(_cats(water=100, fire=90, news=10))
    assert "fire" in result["concurrent"]
    assert "news" not in result["concurrent"]
    for name in result["concurrent"]:
        assert result["effective"][name] >= BREADTH_THRESHOLD


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except Exception:
            failed += 1
            print(f"  FAIL  {t.__name__}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} Tests bestanden")
    sys.exit(1 if failed else 0)

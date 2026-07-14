"""Honest offline analysis for the two-rater CustomerHub AI dataset."""

import csv
import math
import sys
from collections import Counter

try:
    from sklearn.metrics import cohen_kappa_score
    HAVE_SKLEARN = True
except ImportError:
    HAVE_SKLEARN = False


REQUIRED_FIELDS = (
    "rater1_category",
    "rater1_priority",
    "rater2_category",
    "rater2_priority",
    "model_category",
    "model_priority",
)


def manual_kappa(first, second):
    labels = sorted(set(first) | set(second))
    size = len(first)
    observed = sum(a == b for a, b in zip(first, second)) / size
    first_counts = Counter(first)
    second_counts = Counter(second)
    expected = sum(
        (first_counts[label] / size) * (second_counts[label] / size)
        for label in labels
    )
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def kappa_interpretation(value):
    if value < 0:
        return "poor"
    if value < 0.20:
        return "slight"
    if value < 0.40:
        return "fair"
    if value < 0.60:
        return "moderate"
    if value < 0.80:
        return "substantial"
    return "almost perfect"


def wilson_interval(correct, total, z=1.96):
    if total == 0:
        return 0.0, 0.0
    proportion = correct / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(
            proportion * (1 - proportion) / total
            + z * z / (4 * total * total)
        )
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def load_rows(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            ticket_id = row.get("ticket_id", "").strip()
            if not ticket_id:
                continue
            missing = [field for field in REQUIRED_FIELDS if not row.get(field, "").strip()]
            if missing:
                print(f"[skip] {ticket_id}: missing {missing}")
                continue
            for key, value in list(row.items()):
                if key.startswith(("rater", "model_", "adjudicated_")) and value:
                    row[key] = value.strip().lower()
            rows.append(row)
    return rows


def classification_metrics(truth, predicted):
    labels = sorted(set(truth) | set(predicted))
    per_class = {}
    for label in labels:
        true_positive = sum(t == label and p == label for t, p in zip(truth, predicted))
        false_positive = sum(t != label and p == label for t, p in zip(truth, predicted))
        false_negative = sum(t == label and p != label for t, p in zip(truth, predicted))
        support = sum(t == label for t in truth)
        precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
        recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {
            "support": support,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }

    correct = sum(t == p for t, p in zip(truth, predicted))
    count = len(truth)
    return {
        "labels": labels,
        "accuracy": correct / count if count else 0.0,
        "correct": correct,
        "macro_precision": sum(v["precision"] for v in per_class.values()) / len(per_class),
        "macro_recall": sum(v["recall"] for v in per_class.values()) / len(per_class),
        "macro_f1": sum(v["f1"] for v in per_class.values()) / len(per_class),
        "per_class": per_class,
    }


def report(rows, field, title):
    first = [row[f"rater1_{field}"] for row in rows]
    second = [row[f"rater2_{field}"] for row in rows]
    agreement = sum(a == b for a, b in zip(first, second))
    kappa = (
        cohen_kappa_score(first, second)
        if HAVE_SKLEARN
        else manual_kappa(first, second)
    )

    evaluated = []
    disagreements = []
    adjudicated_key = f"adjudicated_{field}"
    for row in rows:
        rater1 = row[f"rater1_{field}"]
        rater2 = row[f"rater2_{field}"]
        adjudicated = row.get(adjudicated_key, "").strip()
        if rater1 == rater2:
            truth = rater1
            source = "consensus"
        elif adjudicated:
            truth = adjudicated
            source = "adjudicated"
        else:
            disagreements.append(row)
            continue
        evaluated.append((row, truth, row[f"model_{field}"], source))

    truth = [item[1] for item in evaluated]
    predicted = [item[2] for item in evaluated]
    metrics = classification_metrics(truth, predicted)
    low, high = wilson_interval(metrics["correct"], len(evaluated))

    print(f"\n{'=' * 72}\n{title.upper()}\n{'=' * 72}")
    print(f"Human agreement: {agreement}/{len(rows)} ({agreement / len(rows):.1%})")
    print(f"Cohen's kappa: {kappa:.3f} [{kappa_interpretation(kappa)}]")
    print(
        f"Model evaluation coverage: {len(evaluated)}/{len(rows)} "
        f"(consensus plus explicit adjudication)"
    )
    if disagreements:
        print(
            f"Excluded unresolved disagreements: "
            f"{', '.join(row['ticket_id'] for row in disagreements)}"
        )

    print(
        f"Accuracy: {metrics['accuracy']:.3f} "
        f"({metrics['correct']}/{len(evaluated)}), Wilson 95% CI [{low:.3f}, {high:.3f}]"
    )
    print(f"Macro precision: {metrics['macro_precision']:.3f}")
    print(f"Macro recall:    {metrics['macro_recall']:.3f}")
    print(f"Macro F1:        {metrics['macro_f1']:.3f}")

    print("\nPer-class metrics:")
    for label in metrics["labels"]:
        item = metrics["per_class"][label]
        print(
            f"  {label:<18} support={item['support']:<3} "
            f"precision={item['precision']:.3f} "
            f"recall={item['recall']:.3f} f1={item['f1']:.3f}"
        )

    print("\nConfusion matrix (rows=true, columns=predicted):")
    print("  true\\pred".ljust(20) + " ".join(label[:10].rjust(10) for label in metrics["labels"]))
    for actual in metrics["labels"]:
        counts = [
            sum(t == actual and p == predicted_label for t, p in zip(truth, predicted))
            for predicted_label in metrics["labels"]
        ]
        print(actual[:18].ljust(20) + " ".join(str(value).rjust(10) for value in counts))

    if disagreements:
        print("\nUnresolved disagreement review (no ticket text or PII):")
        for row in disagreements:
            print(
                f"  {row['ticket_id']}: rater1={row[f'rater1_{field}']}, "
                f"rater2={row[f'rater2_{field}']}, model={row[f'model_{field}']}"
            )


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python analyze_eval.py <fully_labeled.csv>")
    rows = load_rows(sys.argv[1])
    if not rows:
        raise SystemExit("No complete rows found")
    print(f"Loaded {len(rows)} fully labeled, unique ticket rows from {sys.argv[1]}")
    if len({row["ticket_id"] for row in rows}) != len(rows):
        raise SystemExit("Duplicate ticket IDs detected; evaluation aborted")
    report(rows, "category", "Category classification")
    report(rows, "priority", "Priority classification")
    print(
        "\nMethod note: unresolved rater disagreements are never silently assigned "
        "to rater 1. Add adjudicated_category/adjudicated_priority columns only "
        "after a documented third-opinion review."
    )


if __name__ == "__main__":
    main()

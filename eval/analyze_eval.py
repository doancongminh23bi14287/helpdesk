"""
CustomerHub — Post-submission AI Evaluation Analysis
======================================================
Computes the metrics designed in Thesis §IV.14.4 (originally planned for a
100-ticket production study) on a smaller, honestly-labeled two-rater sample.
"""

import sys
import csv
from collections import Counter, defaultdict

try:
    from sklearn.metrics import cohen_kappa_score, precision_recall_fscore_support, accuracy_score
    HAVE_SKLEARN = True
except ImportError:
    HAVE_SKLEARN = False
    print("[warning] scikit-learn not found — falling back to manual formulas.\n"
          "          Install with: pip install scikit-learn --break-system-packages\n")


def manual_kappa(a, b):
    labels = sorted(set(a) | set(b))
    n = len(a)
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pa = Counter(a)
    pb = Counter(b)
    pe = sum((pa[l] / n) * (pb[l] / n) for l in labels)
    if pe == 1:
        return 1.0
    return (po - pe) / (1 - pe)


def manual_prf_macro(y_true, y_pred):
    labels = sorted(set(y_true) | set(y_pred))
    precisions, recalls, f1s = [], [], []
    for lab in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == lab and p == lab)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != lab and p == lab)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == lab and p != lab)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        precisions.append(prec); recalls.append(rec); f1s.append(f1)
    return (sum(precisions) / len(labels), sum(recalls) / len(labels),
            sum(f1s) / len(labels), labels, precisions, recalls, f1s)


def kappa_interpretation(k):
    if k < 0:      return "poor (worse than chance) — do not present this as reliable ground truth"
    if k < 0.20:   return "slight"
    if k < 0.40:   return "fair"
    if k < 0.60:   return "moderate"
    if k < 0.80:   return "substantial"
    return "almost perfect"


def load_rows(path):
    rows = []
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if not row.get('ticket_id', '').strip():
                continue
            missing = [k for k in ('rater1_category', 'rater1_priority',
                                    'rater2_category', 'rater2_priority',
                                    'model_category', 'model_priority')
                       if not row.get(k, '').strip()]
            if missing:
                print(f"[skip] {row['ticket_id']}: missing {missing}")
                continue
            for k in ('rater1_category', 'rater1_priority', 'rater2_category',
                      'rater2_priority', 'model_category', 'model_priority'):
                row[k] = row[k].strip().lower()
            rows.append(row)
    return rows


def majority_label(a, b):
    return a if a == b else a


def report(rows, field, label_name):
    r1 = [r[f'rater1_{field}'] for r in rows]
    r2 = [r[f'rater2_{field}'] for r in rows]
    model = [r[f'model_{field}'] for r in rows]
    truth = [majority_label(a, b) for a, b in zip(r1, r2)]
    agree_n = sum(1 for a, b in zip(r1, r2) if a == b)

    print(f"\n{'=' * 60}")
    print(f"  {label_name.upper()}  (N = {len(rows)})")
    print('=' * 60)
    print(f"Rater agreement: {agree_n}/{len(rows)} tickets "
          f"({100 * agree_n / len(rows):.1f}%)")

    if HAVE_SKLEARN:
        kappa = cohen_kappa_score(r1, r2)
    else:
        kappa = manual_kappa(r1, r2)
    print(f"Cohen's kappa (rater1 vs rater2): {kappa:.3f}  "
          f"[{kappa_interpretation(kappa)}]")

    if agree_n < len(rows):
        print(f"[note] {len(rows) - agree_n} disagreements resolved by taking "
              f"rater1 as ground truth. List them and re-check by hand before "
              f"presenting — a third opinion on disagreements strengthens this.")

    if HAVE_SKLEARN:
        acc = accuracy_score(truth, model)
        prec, rec, f1, _ = precision_recall_fscore_support(
            truth, model, average='macro', zero_division=0)
    else:
        acc = sum(1 for t, m in zip(truth, model) if t == m) / len(truth)
        prec, rec, f1, labels, precs, recs, f1s = manual_prf_macro(truth, model)

    print(f"\nModel accuracy vs ground truth: {acc:.3f}  ({acc*100:.1f}%)")
    print(f"Macro precision: {prec:.3f}")
    print(f"Macro recall:    {rec:.3f}")
    print(f"Macro F1:        {f1:.3f}")

    print(f"\nPer-class breakdown:")
    classes = sorted(set(truth) | set(model))
    for c in classes:
        tp = sum(1 for t, m in zip(truth, model) if t == c and m == c)
        support = sum(1 for t in truth if t == c)
        pred_n = sum(1 for m in model if m == c)
        p = tp / pred_n if pred_n else 0.0
        r = tp / support if support else 0.0
        print(f"  {c:<20} support={support:<3} precision={p:.2f}  recall={r:.2f}")

    errors = [r['ticket_id'] for r, t, m in zip(rows, truth, model) if t != m]
    print(f"\nMisclassified ticket IDs ({len(errors)}): {', '.join(errors) if errors else 'none'}")
    print("  -> Look at these by hand: are they the 'mixed-concern' tickets\n"
          "     your thesis's qualitative finding already predicted?")


def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_eval.py <your_data.csv>")
        sys.exit(1)

    rows = load_rows(sys.argv[1])
    if not rows:
        print("No complete rows found. Fill in every column of the CSV first.")
        sys.exit(1)

    print(f"Loaded {len(rows)} fully-labeled tickets from {sys.argv[1]}")

    report(rows, 'category', 'Category classification')
    report(rows, 'priority', 'Priority classification')

    print(f"\n{'=' * 60}")
    print("  SUMMARY FOR SLIDE B2 / Q&A")
    print('=' * 60)
    print("Copy the accuracy, macro precision/recall, and kappa numbers above")
    print("into slide B2 (box 03/04). State the sample size and that raters")
    print("were you + [name/role of rater 2], labeling independently and blind")
    print("to the model's output and to each other's labels.")


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
CAP-ROC v0.2 (delta gate) — reference calculator

What it does:
- Computes expected alert rate A and PASS/FAIL for average capacity stability (A <= C)
- Optionally computes a δ-level overload gate under a Poisson arrivals model:
    Choose λ_max s.t. P(Poisson(λ_max) > C) <= δ
    Enforce A <= λ_max (and derive FPR_max_δ)

Usage:
  python src/cap_roc_tool.py --R 20 --p 0.01 --tpr 0.85 --fpr 0.30 --C 4
  python src/cap_roc_tool.py --R 20 --p 0.01 --tpr 0.85 --fpr 0.07 --C 4 --delta 0.01

Notes:
- All rates share the same time unit. If R is per day, C is per day.
- δ gate uses an exact Poisson CDF inversion by binary search (no normal approximation).
"""

import argparse
import math

def poisson_cdf(k: int, lam: float) -> float:
    """Poisson CDF P(N<=k) for N~Poisson(lam) via recurrence (lightweight reference)."""
    if k < 0:
        return 0.0
    if lam < 0:
        raise ValueError("lam must be >= 0")
    term = math.exp(-lam)  # i=0
    total = term
    for i in range(1, k + 1):
        term *= lam / i
        total += term
    # clamp
    if total < 0.0:
        return 0.0
    if total > 1.0:
        return 1.0
    return total

def poisson_overload_prob(lam: float, C: int) -> float:
    """P(N > C) for N~Poisson(lam)."""
    return 1.0 - poisson_cdf(C, lam)

def lambda_max_poisson(delta: float, C: int, tol: float = 1e-8) -> float:
    """Largest lam such that P(Poisson(lam) > C) <= delta (exact inversion by binary search)."""
    if not (0.0 < delta < 1.0):
        raise ValueError("delta must be in (0,1)")
    if C < 0:
        raise ValueError("C must be >= 0")

    lo = 0.0
    hi = max(1.0, C + 1.0)

    # Expand hi until overload_prob(hi) > delta (bracket the crossing)
    for _ in range(80):
        if poisson_overload_prob(hi, C) > delta:
            break
        hi *= 2.0
        if hi > 1e6:
            break

    # Binary search
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if poisson_overload_prob(mid, C) > delta:
            hi = mid
        else:
            lo = mid
        if hi - lo < tol * (1.0 + lo):
            break
    return lo

def cap_roc(R: float, p: float, tpr: float, fpr: float, C: float, delta: float | None):
    if R <= 0:
        raise ValueError("R must be > 0")
    if not (0 <= p <= 1):
        raise ValueError("p must be in [0,1]")
    for name, v in [("TPR", tpr), ("FPR", fpr)]:
        if not (0 <= v <= 1):
            raise ValueError(f"{name} must be in [0,1]")
    if C < 0:
        raise ValueError("C must be >= 0")

    A = R * (p * tpr + (1 - p) * fpr)
    passed_mean = A <= C

    fpr_max_mean = float("nan")
    if p < 1:
        fpr_max_mean = (C / R - p * tpr) / (1 - p)

    tpr_max_mean = float("nan")
    if p > 0:
        tpr_max_mean = (C / R - (1 - p) * fpr) / p

    delta_out = None
    if delta is not None:
        C_int = int(round(C))
        lam_max = lambda_max_poisson(delta=delta, C=C_int)
        overload_at_A = poisson_overload_prob(A, C_int)
        passed_delta = A <= lam_max

        fpr_max_delta = float("nan")
        if p < 1:
            fpr_max_delta = (lam_max / R - p * tpr) / (1 - p)

        delta_out = {
            "delta": delta,
            "C_int": C_int,
            "lam_max": lam_max,
            "overload_prob_at_A": overload_at_A,
            "passed_delta": passed_delta,
            "fpr_max_delta_raw": fpr_max_delta
        }

    return {
        "A": A,
        "passed_mean": passed_mean,
        "fpr_max_mean_raw": fpr_max_mean,
        "tpr_max_mean_raw": tpr_max_mean,
        "C_required": A,
        "delta": delta_out
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--R", type=float, required=True, help="incoming items per time unit")
    ap.add_argument("--p", type=float, required=True, help="base anomaly rate (probability)")
    ap.add_argument("--tpr", type=float, required=True, help="true positive rate")
    ap.add_argument("--fpr", type=float, required=True, help="false positive rate")
    ap.add_argument("--C", type=float, required=True, help="human review capacity (alerts per time unit)")
    ap.add_argument("--delta", type=float, default=None, help="optional overload risk target (e.g., 0.01). Enables Poisson δ-gate.")
    args = ap.parse_args()

    out = cap_roc(args.R, args.p, args.tpr, args.fpr, args.C, args.delta)

    print("\nCAP-ROC v0.2 (delta gate)")
    print("-" * 70)
    print(f"Inputs: R={args.R:g}, p={args.p:g}, TPR={args.tpr:g}, FPR={args.fpr:g}, C={args.C:g}")
    print(f"Expected alert rate A = {out['A']:.6g} alerts/time")
    print(f"Mean (expectation) gate: {'PASS' if out['passed_mean'] else 'FAIL'} (A {'<=' if out['passed_mean'] else '>'} C)")

    print("\nDerived (mean gate)")
    print("-" * 70)
    print(f"FPR_max_mean (raw) = {out['fpr_max_mean_raw']:.6g}")
    if math.isfinite(out["fpr_max_mean_raw"]):
        if out["fpr_max_mean_raw"] < 0:
            print("Note: FPR_max_mean < 0 => true positives alone exceed capacity (even if FPR=0).")
        elif out["fpr_max_mean_raw"] > 1:
            print("Note: FPR_max_mean > 1 => capacity is high relative to volume; any valid FPR<=1 satisfies mean gate at this TPR.")
    print(f"C_required = {out['C_required']:.6g} alerts/time (minimum capacity to sustain this operating point)")
    print(f"TPR_max_mean at this FPR (raw) = {out['tpr_max_mean_raw']:.6g}")

    if out["delta"] is not None:
        d = out["delta"]
        print("\nDelta (tail-risk) gate — Poisson model")
        print("-" * 70)
        print(f"Target: P(N > C_int) <= δ with δ={d['delta']:.6g}, C_int={d['C_int']}")
        print(f"λ_max (exact Poisson inversion) = {d['lam_max']:.6g} alerts/time")
        print(f"Overload probability at current A: P(Poisson(A) > C_int) = {d['overload_prob_at_A']:.6g}")
        print(f"Delta gate: {'PASS' if d['passed_delta'] else 'FAIL'} (A {'<=' if d['passed_delta'] else '>'} λ_max)")
        print(f"FPR_max_delta (raw) = {d['fpr_max_delta_raw']:.6g}")
        if math.isfinite(d["fpr_max_delta_raw"]) and d["fpr_max_delta_raw"] < 0:
            print("Note: FPR_max_delta < 0 => even anomaly alerts alone exceed δ-safe mean; increase capacity or narrow scope.")
        print("\nReminder: Poisson assumes independence. If alerts are bursty/correlated, tail risk may be understated; consider an overdispersed model.")
    else:
        print("\nDelta gate: disabled (no --delta provided)")

    print("\nFeasibility reminders")
    print("-" * 70)
    print("Mean gate:   A = R[p*TPR + (1-p)*FPR] <= C")
    if args.delta is not None:
        print("Delta gate:  Find λ_max s.t. P(Poisson(λ_max) > C_int) <= δ; require A <= λ_max")
    print("Mean derived:  FPR <= (C/R - p*TPR)/(1-p)  (if p<1)")
    if args.delta is not None:
        print("Delta derived: FPR <= (λ_max/R - p*TPR)/(1-p)  (if p<1)")

if __name__ == "__main__":
    main()

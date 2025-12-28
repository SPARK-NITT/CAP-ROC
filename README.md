# CAP-ROC v0.2 — Capacity-Constrained ROC Feasibility (delta gate)

CAP-ROC is a deployment **feasibility gate** for rare-event detectors: it couples ROC operating points (TPR/FPR) to **human review capacity** so you can answer one question before you ship:

> **Can humans keep up with the alert stream at this operating point?**

It includes:
- an **expectation gate** (average load stays within capacity), and
- an optional **δ-level overload gate** (tail-risk protection) using exact Poisson tail inversion.

![CAP-ROC Feasibility Map](docs/cap_roc_feasibility_map.png)

![CAP-ROC PASS/FAIL Card](docs/cap_roc_pass_fail_card.png)

---

## Why CAP-ROC exists

Alerting systems often “work” on paper (AUC/accuracy look great) and still fail in reality:
rare events (`p` small) + modest `FPR` + high volume (`R`) ⇒ alert fatigue, backlog, ignored true alerts.

CAP-ROC makes human capacity a **hard constraint**, not an afterthought.

---

## The expectation gate (one line)

Define expected alert rate per time unit:

\[
A = R\,[p\,TPR + (1-p)\,FPR]
\]

A system is **capacity-stable (in expectation)** if:

\[
A \le C
\]

Where:

- `R` = incoming item rate (items / time)
- `p` = base anomaly rate `Pr(anomaly)`
- `TPR` = `Pr(alert | anomaly)`
- `FPR` = `Pr(alert | normal)`
- `C` = sustainable human review capacity (alerts / time)

Equivalent (solve for max allowable false positives):

\[
FPR_{\max} = \frac{C/R - p\,TPR}{1-p}
\]

If `C/R - p*TPR < 0`, you're over capacity even with `FPR = 0`.

---

## The δ (delta) gate (tail-risk protection)

The expectation gate controls the **average** load. The δ gate controls the probability of “bad hours/days.”

Model alerts per time unit as:

\[
\lambda = A = R\,[p\,TPR + (1-p)\,FPR]
\]

\[
N \sim \mathrm{Poisson}(\lambda)
\]

Choose a risk target `δ` (e.g., 0.01) and require:

\[
\Pr(N > C) \le \delta
\]

Define \(\lambda_{\max}(\delta, C)\) as the largest mean such that
\(\Pr(\mathrm{Poisson}(\lambda_{\max}) > C) \le \delta\).
Then the δ gate requires:

\[
A \le \lambda_{\max}(\delta, C)
\]

This implies a δ-level bound on false positives:

\[
FPR_{\max}^{\delta} = \frac{\lambda_{\max}/R - p\,TPR}{1-p}
\]

**Implementation note:** For small capacities (e.g., `C ≤ 10`), normal approximations can be inaccurate.
The reference tool computes \(\lambda_{\max}\) by **exact Poisson tail inversion (binary search)**.

---

## What’s in this repo

- `src/`
  - `cap_roc_tool.py` — reference CLI calculator (supports `--delta`)
- `examples/`
  - `cap_roc_examples.txt` — example runs and notes

---

## Quickstart

### Requirements
- Python 3.9+ (no external packages)

### Run the calculator (expectation gate)

```bash
python src/cap_roc_tool.py --R 20 --p 0.01 --tpr 0.85 --fpr 0.30 --C 4


### Related SPARK-NITT standards

- NITT — digital identity standard  
  https://github.com/SPARK-NITT/nitt-digital-identity-standard
- IRST — transparency for recursive systems  
  https://github.com/SPARK-NITT/IRST-Institute-for-Recursive-Systems-Transparency
- HRIS — coherence-centered refusal (HRIS 3.2.4(b))  
  https://github.com/SPARK-NITT/HRIS-Human-Recursive-Integrity-Standard
- CTGS — consumer transparency governance  
  https://github.com/SPARK-NITT/ctgs-consumer-transparency-standard


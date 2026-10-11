# Ad-to-Landing-Page Message Match Auditor (PS-03)

An offline-first, evidence-grounded compliance auditor that verifies whether a landing page delivers on the promises made in its advertising copy.

---

## Key Differentiators & Engineering Principles

1. **Deterministic Grounding**: Every finding must be grounded in an exact quote verified against the extracted DOM source. Zero hallucination tolerance.
2. **5-State Claim Taxonomy**: Claims are classified as `SUPPORTED`, `CONTRADICTED`, `NOT_FOUND`, `PARTIALLY_SUPPORTED`, or `AMBIGUOUS`. Missing claims are treated as evidence gaps, never as false promises.
3. **Normalized Mathematical Scoring**:
   $$\text{Match Score} = 100 \times \frac{\sum_i w_i \cdot s_i}{\sum_i w_i}$$
   Independent Evidence Coverage Index, Evidence Prominence Index, and Anti-Masking Critical Liability Flags.
4. **Heuristic DOM Zones**: Transparently distinguishes hero-level prominence from buried footer fine print.
5. **Mobile-First Responsive Dashboard**: Touch-friendly metric cards, preset benchmarks, and downloadable CSV/JSON exports.

---

## Project Structure

```
message-match-auditor/
├── app.py                      # Responsive Streamlit UI
├── core/
│   ├── schemas.py              # Pydantic schemas (AtomicClaim, AuditFinding, AuditResult)
│   ├── extractor.py            # DOM block parser & heuristic zone classification
│   ├── claims.py               # Ad decomposer & canonical claim deduplicator
│   ├── matcher.py              # Claim-to-evidence evaluator (numeric, polarity, qualifiers)
│   ├── verifier.py             # Deterministic quote verification
│   ├── scorer.py               # Evidence-weighted score, coverage, & prominence
│   └── audit_engine.py         # End-to-end pipeline orchestrator
├── samples/
│   └── benchmark_cases.json    # Canonical test fixtures
└── tests/
    └── test_pipeline.py        # Automated and metamorphic test suite
```

---

## Installation & Running

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Test Suite
```bash
python -m unittest tests/test_pipeline.py -v
```

### 3. Launch Dashboard
```bash
streamlit run app.py
```

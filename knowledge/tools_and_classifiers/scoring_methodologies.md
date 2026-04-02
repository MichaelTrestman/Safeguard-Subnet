# Scoring Methodologies for AI Red-Teaming

## Overview

How the industry measures the effectiveness of red-teaming and the accuracy of safety evaluation. Relevant to both how Safeguard scores miners and how Safeguard validates its own evaluation pipeline.

---

## 1. Attack Success Rate (ASR)

The primary metric for measuring red-team effectiveness.

### Definition

```
ASR = (Number of successful attacks) / (Total number of attack attempts)
```

An attack is "successful" if the target model produces harmful output in response to the adversarial probe, as determined by a classifier or human judge.

### Variants

| Variant | Definition | Use Case |
|---|---|---|
| ASR@1 | Success rate with one attempt per behavior | Baseline difficulty assessment |
| ASR@k | Success rate with k attempts (success if ANY succeeds) | Miner competence (given multiple tries) |
| Per-category ASR | ASR broken down by harm category | Category coverage assessment |
| Weighted ASR | ASR weighted by harm severity | Risk-adjusted scoring |

### Relevance to Safeguard

- **Miner scoring**: Miners with higher ASR on canaries (known-achievable failures) score higher
- **Target assessment**: ASR across categories gives the safety profile of a target service
- **Caveat**: Raw ASR alone incentivizes sandbagging — miners could achieve 100% ASR by only attempting easy attacks. Must be combined with coverage and difficulty metrics.

---

## 2. Safety Classifier Metrics

For evaluating Safeguard's tier 2 classifier accuracy.

### Standard Classification Metrics

| Metric | Formula | What It Measures |
|---|---|---|
| Precision | TP / (TP + FP) | Of flagged content, how much is actually unsafe? |
| Recall | TP / (TP + FN) | Of all unsafe content, how much did we catch? |
| F1 Score | 2 × (P × R) / (P + R) | Harmonic mean of precision and recall |
| FPR | FP / (FP + TN) | False positive rate — safe content incorrectly flagged |
| FNR | FN / (FN + TP) | False negative rate — unsafe content missed |
| AUPRC | Area under precision-recall curve | Overall ranking quality |

### Safety-Specific Considerations

**In safety classification, false negatives are generally worse than false positives:**
- Missing unsafe content (FN) = real safety failure
- Over-flagging safe content (FP) = annoyance but not safety failure

Therefore, Safeguard's classifier should optimize for **high recall** (catch everything unsafe) while maintaining **acceptable precision** (don't flag everything as unsafe).

**Recommended targets for Safeguard tier 2:**
- Recall ≥ 0.95 (miss < 5% of truly unsafe content)
- Precision ≥ 0.80 (at most 20% of flags are false positives)
- Cases below confidence threshold escalate to tier 3

### Calibration

A well-calibrated classifier means its confidence scores correspond to actual probabilities:
- If the classifier says "90% confidence this is unsafe," it should be right ~90% of the time
- Good calibration enables reliable tier 2 → tier 3 escalation thresholds
- Measured via Expected Calibration Error (ECE) or reliability diagrams

---

## 3. Inter-Annotator Agreement (IAA)

For evaluating Safeguard's HITL submechanism and establishing ground truth.

### Cohen's Kappa (κ)

Measures agreement between two annotators, corrected for chance agreement.

```
κ = (observed agreement - chance agreement) / (1 - chance agreement)
```

| κ Value | Interpretation |
|---|---|
| < 0 | Less than chance agreement |
| 0.01 - 0.20 | Slight agreement |
| 0.21 - 0.40 | Fair agreement |
| 0.41 - 0.60 | Moderate agreement |
| 0.61 - 0.80 | Substantial agreement |
| 0.81 - 1.00 | Almost perfect agreement |

**Target for Safeguard HITL**: κ ≥ 0.61 (substantial agreement) for consensus labels to be usable as training data.

### Fleiss' Kappa

Extension of Cohen's κ for more than two annotators. Used when multiple human miners independently label the same case.

### Krippendorff's Alpha

More general IAA metric that handles:
- Any number of annotators
- Missing data (not all annotators label all cases)
- Multiple data types (nominal, ordinal, interval, ratio)

**Recommended for Safeguard HITL** because it handles the realistic case where not all human miners label every case.

### Relevance to Safeguard HITL Scoring

```
Human miner quality = f(
  gold_standard_accuracy,    # Performance on known-label cases
  consensus_alignment,        # Agreement with other labelers (IAA)
  consistency,               # Same answer when given same case twice
  response_time              # Not too fast (random) or too slow (inactive)
)
```

---

## 4. Novelty Scoring

For evaluating whether miners are finding new attack vectors vs. repeating known attacks.

### Embedding-Based Deduplication

1. Embed all miner probe transcripts using a text embedding model
2. Compute cosine similarity between new probes and existing probe database
3. Novel probes (low similarity to existing) score higher

```
novelty_score = 1 - max(cosine_similarity(new_probe, existing_probes))
```

### Semantic Clustering

- Cluster probe transcripts by attack strategy
- Miners who open new clusters (new attack strategies) score highest
- Miners who contribute to existing clusters score lower (diminishing returns)
- Miners who submit near-duplicates of existing probes score lowest

### Known Attack Database Comparison

Compare miner probes against databases of known attacks:
- HarmBench attack prompts
- Jailbreak chat archives
- Published attack papers' examples
- Previously submitted probes in Safeguard

Novel attacks (not matching known patterns) receive bonus scoring.

---

## 5. Coverage Metrics

For evaluating breadth of red-teaming.

### Category Coverage

```
coverage = |categories_tested| / |total_categories|
```

Miners should be penalized for only testing easy categories and ignoring hard ones.

### Technique Diversity

Using the attack technique taxonomy (see taxonomies/attack_techniques.md):

```
technique_diversity = |unique_techniques_used| / |available_techniques|
```

### Depth Score

Measuring sophistication of multi-turn probing:
- Single-turn direct request = low depth
- Multi-turn gradual escalation = high depth
- Number of turns, topic transitions, and strategy adaptations

---

## 6. Composite Scoring for Safeguard Miners

Bringing it all together — a proposed composite scoring formula:

```
miner_score = w1 * canary_accuracy     # Did you find known failures? Avoid false flags?
            + w2 * coverage_score       # Did you probe all assigned categories?
            + w3 * novelty_score        # Did you find new attack vectors?
            + w4 * depth_score          # How sophisticated were your probes?
```

### Weight Suggestions

| Component | Weight | Rationale |
|---|---|---|
| Canary accuracy | 0.35 | Core competence — must find known failures AND avoid false flags |
| Coverage | 0.25 | Breadth matters — can't ignore categories |
| Novelty | 0.25 | The network's primary value — finding new failures |
| Depth | 0.15 | Incentivize sophisticated probing over shallow spraying |

### Anti-Gaming Measures

1. **Canary accuracy prevents sandbagging**: Miners must find known failures
2. **Negative canaries prevent over-flagging**: Miners must not flag safe content
3. **Novelty prevents replay**: Repeating known attacks earns less
4. **Coverage prevents cherry-picking**: Must test across categories
5. **Canary indistinguishability**: Miners can't tell canaries from real tasks

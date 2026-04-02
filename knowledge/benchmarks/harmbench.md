# HarmBench: A Standardized Evaluation Framework for Automated Red Teaming and Robust Refusal

**Paper**: "HarmBench: A Standardized Evaluation Framework for Automated Red Teaming and Robust Refusal"
**Authors**: Mazeika, Long, Haize Labs, Yin, et al.
**Published**: February 2024 (arXiv:2402.04249)
**Code**: https://github.com/centerforaisafety/HarmBench
**License**: MIT

## Overview

HarmBench is a standardized framework for evaluating both red-teaming attack methods and safety defenses (robust refusal) in LLMs. It is the most comprehensive benchmark in this space and directly relevant to Safeguard's design — the DESIGN.md explicitly references "HarmBench-style" classifiers.

## Key Components

### 1. Standardized Behavior Taxonomy

HarmBench defines a taxonomy of **harmful behaviors** organized into semantic categories:

**Functional categories**:
- **Standard behaviors**: Direct harmful requests (e.g., "Write instructions for synthesizing [chemical]")
- **Contextual behaviors**: Requests that are harmful only in certain contexts
- **Copyright behaviors**: Requests to reproduce copyrighted content
- **Multimodal behaviors**: Harmful requests involving image inputs

**Semantic categories** (harm types):
- Chemical & biological weapons
- Cybercrime & hacking
- Harassment & bullying
- Illegal activities
- Misinformation & disinformation
- Copyright violations
- Self-harm & suicide
- Sexual content
- Violence & physical harm
- Weapons & explosives
- Fraud & deception
- Privacy violations
- Hate speech & discrimination

### 2. Attack Methods Evaluated

HarmBench evaluates a standardized set of red-teaming attack methods:

| Method | Type | Description |
|---|---|---|
| GCG | Optimization | Greedy Coordinate Gradient — optimizes adversarial suffixes |
| AutoDAN | Optimization | Automated generation of jailbreak prompts via genetic algorithm |
| PAIR | LLM-based | Prompt Automatic Iterative Refinement — uses an attacker LLM |
| TAP | LLM-based | Tree of Attacks with Pruning — tree search over attack strategies |
| PAP | LLM-based | Persuasion-based attack prompts |
| DirectRequest | Baseline | Simple direct harmful request (no attack strategy) |
| HumanJailbreaks | Manual | Curated human-written jailbreak templates |
| FewShot | In-context | Uses few-shot examples to prime harmful behavior |
| MultilingualJailbreak | Transfer | Uses non-English languages to bypass safety training |

### 3. Classifier for Evaluation

HarmBench introduces a **fine-tuned classifier** for determining whether an LLM response constitutes a successful attack (i.e., the model complied with the harmful request). This is the "HarmBench-style classifier" referenced in Safeguard's DESIGN.md.

**Classifier details**:
- Based on Llama 2 13B (fine-tuned)
- Binary classification: harmful compliance vs. refusal
- Trained on human-annotated attack/response pairs
- Achieves ~95% agreement with human annotators
- Significantly more reliable than GPT-4-as-judge for this task
- Available as open-source model weights

**Why this matters for Safeguard**: The tier 2 "lightweight classifier" in Safeguard's tiered validation can be modeled after this. A fine-tuned classifier is:
- Much cheaper than an LLM judge (single forward pass)
- More reliable than prompt-based evaluation for clear cases
- Well-suited for the "confident middle" of the distribution

### 4. Key Findings

- **No single defense is robust against all attacks**: Models that resist one attack method often fall to others
- **Attack transferability**: Attacks optimized against one model often work on others
- **Context matters**: The same request can be harmful or benign depending on context
- **Classifier reliability**: Fine-tuned classifiers significantly outperform prompted LLM judges for binary safety classification
- **Attack Success Rate (ASR)** is the standard metric: percentage of test behaviors where at least one attack attempt succeeds

## Metrics

### Attack Success Rate (ASR)

The primary metric. For a set of harmful behaviors B and an attack method A against target model M:

```
ASR = |{b in B : A successfully elicits harmful response from M for b}| / |B|
```

Variants:
- **ASR@1**: Success rate with a single attack attempt per behavior
- **ASR@k**: Success rate with k attempts (success if any attempt succeeds)
- **Per-category ASR**: Breakdown by harm category

### Refusal Rate

For defense evaluation — the percentage of harmful requests that the model successfully refuses.

## Using This for Safeguard

1. **Adopt the harm taxonomy** as a starting point for Safeguard's probing categories
2. **Use the classifier architecture** as the basis for Safeguard's tier 2 validation
3. **Implement ASR as a scoring component** — miners who achieve higher ASR on canaries score higher
4. **Test multiple attack methods** — miners should not be limited to a single approach
5. **The contextual behavior category** is particularly relevant — Safeguard needs to handle cases where the same probe might be harmful or benign depending on context

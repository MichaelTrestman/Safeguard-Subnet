# Open-Source AI Safety Classifiers

## Overview

Safety classifiers are models that evaluate whether AI inputs or outputs are safe or harmful. Safeguard's tier 2 validation uses a "lightweight classifier (HarmBench-style)" for automated scoring. This document surveys the available options.

---

## LlamaGuard Family (Meta)

### LlamaGuard 1
**Paper**: https://arxiv.org/abs/2312.06674
**Model**: https://huggingface.co/meta-llama/LlamaGuard-7b
**Base model**: Llama 2 7B
**Released**: December 2023

**Capabilities**:
- Classifies both inputs (prompts) and outputs (responses) as safe/unsafe
- Supports custom safety taxonomies via system prompt
- Returns the specific violated category
- Default taxonomy: 6 categories (violence, sexual, criminal, firearms, regulated substances, self-harm)

**Performance**: ~86% F1 on their benchmark, competitive with GPT-4 as judge

### LlamaGuard 2
**Model**: https://huggingface.co/meta-llama/Meta-Llama-Guard-2-8B
**Base model**: Llama 3 8B
**Released**: April 2024

**Improvements over v1**:
- Based on stronger base model (Llama 3 vs Llama 2)
- Expanded taxonomy aligned with MLCommons AI Safety v0.5
- 11 hazard categories (matches MLCommons S1-S11)
- Better performance on multilingual inputs
- More robust to adversarial inputs

### LlamaGuard 3
**Model**: https://huggingface.co/meta-llama/Llama-Guard-3-8B
**Base model**: Llama 3.1 8B
**Released**: July 2024

**Improvements**:
- 14 hazard categories (adds elections, code interpreter abuse, defamation)
- Improved multilingual support (8 languages)
- Better calibration on borderline cases

### LlamaGuard 3 1B
**Model**: https://huggingface.co/meta-llama/Llama-Guard-3-1B
**Base model**: Llama 3.2 1B
**Released**: September 2024

**Key advantage**: 1B parameters — fast enough for real-time classification. Suitable for Safeguard's tier 2 where cost and speed matter.

### LlamaGuard 3 11B Vision
**Model**: https://huggingface.co/meta-llama/Llama-Guard-3-11B-Vision
**Base model**: Llama 3.2 11B Vision
**Released**: September 2024

**Key advantage**: Multimodal — can classify image inputs. Relevant for image-generation subnet targets.

### Using LlamaGuard for Safeguard Tier 2

```python
# Example: Using LlamaGuard for automated safety classification
from transformers import AutoModelForCausalLM, AutoTokenizer

model_id = "meta-llama/Llama-Guard-3-1B"  # fast, cheap
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(model_id)

# Format: conversation to classify
conversation = [
    {"role": "user", "content": "[adversarial probe]"},
    {"role": "assistant", "content": "[target response]"}
]

# LlamaGuard returns "safe" or "unsafe\nS[category_number]"
```

**Recommended for Safeguard**: LlamaGuard 3 1B for tier 2 (fast, cheap), LlamaGuard 3 8B for tier 3 validation of tier 2 edge cases.

---

## WildGuard (Allen AI)

**Paper**: https://arxiv.org/abs/2406.18495
**Model**: https://huggingface.co/allenai/wildguard
**Base model**: Mistral 7B
**Released**: June 2024

**Capabilities**:
Three-task classification in a single forward pass:
1. **Prompt harmfulness**: Is the user's input harmful?
2. **Response harmfulness**: Is the model's response harmful?
3. **Response refusal**: Did the model refuse the request?

**Key advantage for Safeguard**: The three-task design maps perfectly to Safeguard's needs:
- Prompt harmfulness → Was the miner's probe actually adversarial? (anti-sandbagging)
- Response harmfulness → Did the target service produce unsafe content?
- Response refusal → Did the target service appropriately refuse?

**Training data**: WildGuardMix — 92K items combining synthetic adversarial examples and real-world conversations.

**Performance**: Outperforms LlamaGuard 2 and GPT-4 on their benchmark, especially on adversarial prompts and refusal detection.

---

## ShieldGemma (Google)

**Models**: https://huggingface.co/collections/google/shieldgemma
**Base models**: Gemma 2B, 9B, 27B
**Released**: July 2024

**Capabilities**:
- Content safety classifier
- Categories: Sexually explicit, dangerous content, harassment, hate speech
- Supports both input and output classification
- Available in three sizes for different cost/performance tradeoffs

**Key advantage**: Multiple size options allow deployment flexibility:
- 2B: Fastest, suitable for high-volume screening
- 9B: Balanced
- 27B: Most accurate, suitable for edge cases

---

## Aegis Guard (NVIDIA)

**Model**: https://huggingface.co/nvidia/Aegis-AI-Content-Safety-LlamaGuard-Defensive-1.0
**Base model**: LlamaGuard fine-tune
**Released**: 2024

**Capabilities**:
- Based on LlamaGuard with additional fine-tuning
- Focused on "defensive" content moderation
- 13 harm categories
- Designed for production deployment

---

## HarmBench Classifier

**Source**: https://github.com/centerforaisafety/HarmBench
**Base model**: Llama 2 13B (fine-tuned)
**Released**: February 2024

**Capabilities**:
- Binary classification: Did the model comply with the harmful request?
- Specifically designed for evaluating red-team attack success
- Trained on human-annotated attack/response pairs
- ~95% agreement with human annotators

**Key advantage for Safeguard**: This is the most directly relevant classifier — it's specifically designed to evaluate whether a red-team attack succeeded, which is exactly what Safeguard tier 2 needs to do.

---

## Comparison Matrix

| Classifier | Size | Multi-task | Categories | Speed | Best For |
|---|---|---|---|---|---|
| LlamaGuard 3 1B | 1B | No | 14 | Fastest | High-volume tier 2 screening |
| LlamaGuard 3 8B | 8B | No | 14 | Medium | Balanced tier 2/3 |
| WildGuard | 7B | Yes (3 tasks) | Per-task | Medium | Comprehensive probe evaluation |
| ShieldGemma 2B | 2B | No | 4 | Fast | Lightweight screening |
| ShieldGemma 27B | 27B | No | 4 | Slow | High-accuracy edge cases |
| HarmBench Classifier | 13B | No | Binary | Medium | Attack success evaluation |

## Recommended Tiered Deployment for Safeguard

```
Tier 1: Canary calibration (no classifier needed — deterministic ground truth)

Tier 2: LlamaGuard 3 1B or WildGuard
  - Fast, single forward pass
  - Handles the confident middle of the distribution
  - Flag low-confidence cases for escalation

Tier 3: LlamaGuard 3 8B + HarmBench Classifier
  - More capable models for ambiguous cases
  - Cross-validate: if both agree → use that label
  - If they disagree → escalate to HITL

Tier 4: HITL (human miners label the hard cases)
```

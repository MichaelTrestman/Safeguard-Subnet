# Large Reasoning Models as Autonomous Jailbreak Agents

Published in Nature Communications 2026 by Hagendorff, Derner, and Oliver.

## Key Finding

Four large reasoning models (DeepSeek-R1, Gemini 2.5 Flash, Grok 3 Mini, Qwen3 235B) were tested as autonomous adversaries conducting multi-turn conversations with nine target models. Result: **97.14% overall jailbreak success rate**.

## Alignment Regression

The paper introduces "alignment regression" — successive generations of capable models paradoxically erode alignment by repurposing advanced reasoning to undermine earlier models' safety mechanisms. Jailbreaking shifts from bespoke, labor-intensive exercise to scalable commodity capability.

## Attack Success Rates (2025-2026 landscape)

| Attack Type | Success Rate | Source |
|-------------|-------------|--------|
| Advanced automated attacks (open-weight targets) | 90-99% | TechRxiv survey |
| Black-box attacks (proprietary models) | 80-94% | Various |
| Agent-driven multi-turn | 95% | Nature Comms 2026 |
| Sophisticated attackers, 10 attempts | ~50% against best-defended | Various |
| JBFuzz fuzzing framework | ~99% across GPT-4o, Gemini 2.0 | JBFuzz paper |
| AutoDAN-Turbo (ICLR 2025) | 88.5-93.4% on GPT-4 | arXiv:2410.05295 |

## Notable New Techniques (2025-2026)

- **DiffusionAttacker** (EMNLP 2025): Seq2seq diffusion model for flexible token modifications preserving semantics. [ACL Anthology](https://aclanthology.org/2025.emnlp-main.1128/)
- **HILL (Hiding Intention by Learning from LLMs)**: Systematically reframes harmful queries into learning-oriented prompts. [arXiv](https://arxiv.org/html/2509.14297v1)
- **PAPILLON** (USENIX Security 2025): Fuzz testing for LLM jailbreaking
- **TwinBreak** (USENIX Security 2025): Exploits security alignment weaknesses
- **Crescendo proven effective against Circuit Breakers** (2025): Multi-turn attacks break even representation-engineering defenses

## Defense

- **ProAct**: Provides "spurious responses" that appear successful but contain no harmful content, causing adversarial search to terminate prematurely. [OpenReview](https://openreview.net/forum?id=pq6rx9r6Aj)
- **JBDistill**: Renewable benchmark enabling efficient jailbreak safety evaluation. [TechXplore](https://techxplore.com/news/2026-03-renewable-benchmark-llm-jailbreak-safety.html)

## Relevance to Safeguard

This research validates that automated red-teaming can achieve near-universal jailbreak rates. The alignment regression finding means that newer reasoning models are *more* effective as attackers, not less. This is both a threat (harder to defend) and an opportunity (Safeguard miners using reasoning models as attackers will be highly effective).

## Sources

- [Nature Communications paper](https://www.nature.com/articles/s41467-026-69010-1)
- [arXiv preprint](https://arxiv.org/abs/2508.04039)
- [JailbreakBench](https://jailbreakbench.github.io/)
- [Comprehensive Jailbreak Survey 2026 (TechRxiv)](https://www.techrxiv.org/users/1011181/articles/1373070/master/file/data/Jailbreaking_LLMs_2026/Jailbreaking_LLMs_2026.pdf)

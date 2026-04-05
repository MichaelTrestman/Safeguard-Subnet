# Safety Benchmarks (2025-2026)

## HELM Safety v1.0
Collection of 5 benchmarks spanning 6 risk categories (violence, fraud, discrimination, sexual content, harassment, deception), evaluating 24 models.

Source: [Stanford CRFM](https://crfm.stanford.edu/2024/11/08/helm-safety.html)

## AIR-Bench 2024
First safety benchmark aligned with government regulations and company policies. Decomposes 8 regulations and 16 policies into **314 granular risk categories** with 5,694 curated prompts. Available on HELM.

Source: [arXiv](https://arxiv.org/html/2407.17436v1) | [HELM](https://crfm.stanford.edu/helm/air-bench/latest/)

## DEF CON Generative Red Teaming Challenge (GRT-2, 2024)
Focused on systemic model flaws rather than individual jailbreaks. Key finding: most successful strategies were hard to distinguish from traditional prompt engineering — role-play requests (3.9% success for "write me a poem about..."), "tell me a story" framings (8.7% success). 2024 Transparency Report published September 2025.

Source: [CSET Analysis](https://cset.georgetown.edu/article/how-i-won-def-cons-generative-ai-red-teaming-challenge/) | [Transparency Report PDF](https://humane-intelligence.org/wp-content/uploads/2025/09/2024-GenerativeAI-RedTeaming-TransparencyReport.pdf)

## AIRTBench (Dreadnode, 2025)
First benchmark for autonomous AI red-teaming capability. Measures how well AI systems can independently discover vulnerabilities.

Source: [arXiv](https://arxiv.org/abs/2506.14682)

## JailbreakBench
Centralized benchmark with repository of jailbreak artifacts and evolving dataset of state-of-the-art adversarial prompts.

Source: [JailbreakBench](https://jailbreakbench.github.io/)

## Scale AI SEAL Adversarial Robustness Leaderboard
Commercial benchmark ranking model robustness against adversarial attacks.

Source: [Scale Leaderboard](https://scale.com/leaderboard/adversarial_robustness)

## Haize Labs Red-Teaming Resistance Leaderboard
Ranks models by resistance to automated red-teaming attacks.

Source: [Hugging Face](https://huggingface.co/blog/leaderboard-haizelab)

## RiskRubric.ai (September 2025)
First AI model risk leaderboard. Generally available for public model risk assessment.

Source: [PR Newswire](https://www.prnewswire.com/news-releases/riskrubricai-now-generally-available-as-the-first-ever-ai-model-risk-leaderboard-302559782.html)

## Meta-Analysis: "How Should AI Safety Benchmarks Benchmark Safety?" (January 2026)
Critical analysis of what safety benchmarks actually measure vs. what they claim to measure. Identifies gaps between benchmark performance and real-world safety.

Source: [arXiv](https://arxiv.org/html/2601.23112v1)

## DeepTeam (November 2025)
Open-source red-teaming framework with 80+ vulnerability types.

Source: [GitHub](https://github.com/confident-ai/deepteam)

## Relevance to Safeguard

These benchmarks provide:
- Calibration targets for Safeguard's scoring (our findings should correlate with established benchmarks)
- Prompt libraries for canary generation
- Methodology reference for evaluation design
- Competitive benchmarking (how does Safeguard's detection compare?)

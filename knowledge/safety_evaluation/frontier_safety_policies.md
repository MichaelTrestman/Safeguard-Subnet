# Frontier AI Safety Policies Comparison

## Overview

METR's December 2025 analysis covers sixteen companies that committed to frontier AI safety protocols at the AI Seoul Summit (May 2024). Twelve have published policies.

## Company Frameworks

### Anthropic RSP v3.0 (effective Feb 24, 2026)
- **ASL-3 activated** provisionally for Claude Opus 4 (May 2025) — targeting models that could assist individuals with undergraduate STEM backgrounds in creating CBRN weapons
- Evaluation interval extended to 6 months
- Added capability checkpoint: ability to autonomously perform 2-8 hour software engineering tasks
- ASL-4 and beyond remain largely undefined

Sources: [RSP v3.0](https://www.anthropic.com/news/responsible-scaling-policy-v3) | [ASL-3 Activation](https://www.anthropic.com/news/activating-asl3-protections) | [GovAI Analysis](https://www.governance.ai/analysis/anthropics-rsp-v3-0-how-it-works-whats-changed-and-some-reflections)

### OpenAI Preparedness Framework v2 (April 2025)
- Capability Reports and Safeguards Reports paralleling Anthropic's RSP
- Critique (arXiv 2509.24394): framework "does not guarantee any AI risk mitigation practices"

Sources: [Framework v2 PDF](https://cdn.openai.com/pdf/18a02b5d-6b67-4cec-ab64-68cdfbddebcd/preparedness-framework-v2.pdf) | [Critique](https://arxiv.org/abs/2509.24394)

### Google DeepMind Frontier Safety Framework v3 (September 2025)
- Added Critical Capability Level for **harmful manipulation** — models with powerful manipulative capabilities that could systematically change beliefs/behaviors in high-stakes contexts
- Covers misuse risk, ML R&D risk, and misalignment risk

Sources: [FSF v3 Announcement](https://deepmind.google/blog/strengthening-our-frontier-safety-framework/) | [FSF v3 PDF](https://storage.googleapis.com/deepmind-media/DeepMind.com/Blog/strengthening-our-frontier-safety-framework/frontier-safety-framework_3.pdf)

## FLI AI Safety Index (Winter 2025)

Evaluates leading AI companies on 33 indicators across six domains:
- **Anthropic**: C+ (highest overall), D for existential safety
- **OpenAI**: C
- **Google DeepMind**: Below OpenAI
- **xAI, Z.ai, Meta, DeepSeek, Alibaba Cloud**: Substantially lower

Critical finding: even the highest-scoring company received a **D for existential safety**.

Sources: [FLI Safety Index](https://futureoflife.org/ai-safety-index-winter-2025/) | [Full Report PDF](https://futureoflife.org/wp-content/uploads/2025/12/AI-Safety-Index-Report_011225_Full_Report_Digital.pdf)

## UK AISI Evaluations

Evaluated 30+ frontier AI models since November 2023. Key findings:
- Cyber: Models complete apprentice-level tasks 50% of the time (up from 9% in late 2023). First model completing expert-level tasks tested in 2025.
- Autonomy: Models complete hour-long software tasks at >40% success (up from <5% in late 2023).

Sources: [Frontier AI Trends Report](https://www.aisi.gov.uk/research/aisi-frontier-ai-trends-report-2025) | [AISI 2025 Year in Review](https://www.aisi.gov.uk/blog/our-2025-year-in-review)

## International AI Safety Report 2026 (February 2026)

Led by Yoshua Bengio, 100+ international experts:
- AI capabilities advancing faster than ability to implement safeguards — gap is widening
- Models can sometimes detect when they are being safety-tested and alter behavior
- AI-generated content produces measurable changes in people's beliefs

Sources: [Report](https://internationalaisafetyreport.org/) | [arXiv](https://arxiv.org/abs/2501.17805)

## Relevance to Safeguard

These frameworks define what the industry considers safety-critical capabilities and evaluation requirements. Safeguard's testing categories should align with the capability thresholds defined by these frameworks (CBRN, cyberattacks, autonomous replication, manipulation). The FLI index gap (everyone gets D on existential safety) validates the need for independent, continuous evaluation.

## Additional Sources

- [METR Common Elements Report](https://metr.org/common-elements)
- [Frontier Model Forum Publications](https://www.frontiermodelforum.org/publications/)
- [NIST IR 8596 Cybersecurity Framework for AI](https://csrc.nist.gov/pubs/ir/8596/iprd)

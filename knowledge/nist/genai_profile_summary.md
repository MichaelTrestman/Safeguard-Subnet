# NIST AI 600-1: Generative AI Profile

**Document**: NIST AI 600-1 — Artificial Intelligence Risk Management Framework: Generative AI Profile
**Published**: July 2024
**Source**: https://airc.nist.gov/Docs/1
**Full PDF**: https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf

## Overview

AI 600-1 is a companion document to the AI RMF (AI 100-1) that specifically addresses risks unique to generative AI systems, including large language models. It identifies 12 risks unique to or exacerbated by GAI and provides detailed guidance for managing them. This is the single most authoritative US government document on GenAI-specific risks.

## The 12 GAI Risks

### 1. CBRN Information or Capabilities
Generative AI may facilitate access to information about chemical, biological, radiological, or nuclear (CBRN) weapons. Models may lower the barrier to acquiring dangerous knowledge.

**Safeguard relevance**: Core red-teaming category — probing whether target services provide CBRN information.

### 2. Confabulation (Hallucination)
Generation of false information presented as fact. Includes fabricated citations, false statistics, made-up entities.

**Safeguard relevance**: Relevant for subnets providing factual/advisory services.

### 3. Data Privacy
Risks from training data memorization and regurgitation, including PII, copyrighted content, and trade secrets.

**Safeguard relevance**: PII extraction probing is a key Safeguard category.

### 4. Environmental Impacts
Energy consumption and carbon footprint of GAI training and inference.

**Safeguard relevance**: Not directly testable via red-teaming.

### 5. Harmful Bias and Homogenization
Systematic biases in generated content, including stereotyping, representational harm, and monoculture effects.

**Safeguard relevance**: Testable through targeted probing for biased outputs.

### 6. Human-AI Configuration
Risks from over-reliance on AI, automation bias, and inappropriate human-AI interaction patterns.

**Safeguard relevance**: Relevant for agent-based subnet services.

### 7. Information Integrity
Generation of misinformation, deepfakes, and content that undermines public trust.

**Safeguard relevance**: Testable through probing for misinformation generation.

### 8. Information Security
Novel attack vectors including prompt injection, data poisoning, model theft, and adversarial inputs.

**Safeguard relevance**: Core red-teaming category — prompt injection and jailbreaks.

### 9. Intellectual Property
Copyright and IP risks from training data and generated outputs.

**Safeguard relevance**: Testable through probing for copyrighted content reproduction.

### 10. Obscene, Degrading, and/or Abusive Content
Generation of explicit, violent, hateful, or otherwise harmful content.

**Safeguard relevance**: Core red-teaming category — the primary "safety failure" most red-teaming targets.

### 11. Value Chain and Component Integration
Risks from third-party components, fine-tuning, and deployment pipelines.

**Safeguard relevance**: Less directly testable, but relevant for supply-chain assessments.

### 12. Dangerous or Violent Recommendations
AI providing advice that could lead to physical harm, including self-harm, violence, or dangerous activities.

**Safeguard relevance**: Core red-teaming category.

## Red-Teaming Guidance in AI 600-1

The document provides extensive guidance on red-teaming for GenAI systems:

### Recommended Red-Teaming Practices

1. **Structured exercises**: Use defined attack taxonomies and systematic coverage of risk categories
2. **Diverse teams**: Include technical experts, domain experts, and representatives of affected communities
3. **Automated + human**: Combine automated adversarial testing with human-driven red-teaming
4. **Continuous testing**: Red-team throughout the lifecycle, not just pre-deployment
5. **Documentation**: Maintain detailed records of red-teaming activities, findings, and remediations

### Specific Testing Recommendations

For each of the 12 risks, the document provides:
- **Suggested actions** for the GOVERN, MAP, MEASURE, and MANAGE functions
- **Metrics and benchmarks** to evaluate risk levels
- **Red-teaming prompts and approaches** relevant to each risk

### Key Quote on Red-Teaming

> "Structured public red-teaming exercises for GAI [...] can be useful for identifying potential risks and harms, evaluating the efficacy of guardrails, and informing risk management decisions."

## Using This for Safeguard

1. **The 12 GAI risks provide a government-sanctioned harm taxonomy** that complements OWASP and HarmBench
2. **NIST explicitly recommends automated + human red-teaming** — this validates Safeguard's architecture (AI miners + HITL)
3. **Continuous testing is explicitly called for** — Safeguard's always-on model fulfills this
4. **The structured exercise approach** maps to Safeguard's per-subnet submechanisms
5. **Documentation requirements** are met by Safeguard's transcript storage and evaluation records
6. **Regulatory weight**: NIST frameworks are referenced by the White House EO and increasingly by procurement requirements — subnet operators who consume Safeguard scores can cite NIST compliance

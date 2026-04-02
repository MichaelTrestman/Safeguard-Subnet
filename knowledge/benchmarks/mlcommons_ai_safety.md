# MLCommons AI Safety Benchmark

**Source**: https://mlcommons.org/benchmarks/ai-safety/
**Version**: v0.5 (April 2024)
**Paper**: "Introducing v0.5 of the AI Safety Benchmark from MLCommons" (arXiv:2404.12241)
**License**: Apache 2.0

## Overview

MLCommons AI Safety is an industry-consortium benchmark for evaluating the safety of AI chat systems. It provides standardized test prompts, a hazard taxonomy, and a grading methodology. MLCommons is the same consortium behind MLPerf (the industry-standard ML performance benchmark), so this carries significant institutional weight.

## Hazard Taxonomy (v0.5)

The benchmark defines **13 hazard categories** based on a mapping to the EU AI Act and other regulatory frameworks:

### Categories

| ID | Hazard Category | Description |
|---|---|---|
| S1 | Violent Crimes | Content enabling or promoting violence, assault, murder, terrorism |
| S2 | Non-Violent Crimes | Fraud, theft, cybercrime, drug-related crimes |
| S3 | Sex-Related Crimes | CSAM, sexual exploitation, trafficking |
| S4 | Child Sexual Exploitation | Specifically CSAM generation and distribution |
| S5 | Defamation | False statements damaging reputation |
| S6 | Specialized Advice | Unqualified medical, legal, financial advice |
| S7 | Privacy | PII exposure, surveillance, tracking |
| S8 | Intellectual Property | Copyright/trademark violation |
| S9 | Indiscriminate Weapons | CBRN weapons, explosives |
| S10 | Hate | Hate speech, discrimination, slurs |
| S11 | Suicide & Self-Harm | Self-harm instructions, suicide promotion |
| S12 | Sexual Content | Explicit sexual content generation |
| S13 | Elections | Election misinformation, voter manipulation |

### Mapping to Regulatory Frameworks

The taxonomy explicitly maps to:
- **EU AI Act**: Article 5 prohibited practices, Annex III high-risk systems
- **NIST AI RMF**: Map types, Measure categories
- **White House EO 14110**: Safety and security requirements

This regulatory grounding is valuable for Safeguard's legitimacy.

## Benchmark Structure

### Test Prompts (Personas)

The benchmark uses **persona-based prompting** to test different user types:
- **Typical user**: Average user asking questions
- **Malicious user**: User attempting to extract harmful content
- Each persona gets prompts across all hazard categories

### Grading System

Models receive grades per hazard category:
- Uses a fine-tuned safety classifier (LlamaGuard-based) to determine if responses are safe or unsafe
- Computes pass rates per category
- Assigns letter grades (A-F) based on pass rates
- Overall safety grade is the worst grade across categories

### Reference Implementations

The benchmark provides:
- Standardized test prompts (thousands per category)
- Reference classifier for automated grading
- Evaluation pipeline code
- Leaderboard infrastructure

## Key Design Decisions Relevant to Safeguard

1. **Worst-category grading**: A model's overall safety is its worst category. This aligns with Safeguard's need to catch ALL categories of failure, not just average performance.

2. **Persona-based testing**: Testing with different simulated user types maps well to Safeguard's miner design — miners should simulate different adversarial personas.

3. **Regulatory alignment**: The explicit mapping to EU AI Act and NIST frameworks gives the taxonomy legal grounding.

4. **Classifier-based evaluation**: Using LlamaGuard-family classifiers for automated grading validates Safeguard's tier 2 approach.

5. **v0.5 limitations acknowledged**: The benchmark explicitly states it does NOT test:
   - Multi-turn conversations (only single-turn)
   - Indirect prompt injection
   - Agent/tool-use scenarios
   - Multimodal inputs
   
   These gaps are exactly what Safeguard's red-team miners can fill — multi-turn adversarial conversations and agent probing.

## Using This for Safeguard

- **Adopt the S1-S13 hazard taxonomy** as one input to Safeguard's harm categories (merge with OWASP and HarmBench)
- **The regulatory mappings** provide justification for why each category matters
- **The grading methodology** (worst-category) is a useful model for scoring target services
- **The gaps** (no multi-turn, no agents, no indirect injection) are Safeguard's value proposition — the subnet provides what static benchmarks cannot

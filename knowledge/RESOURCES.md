# Safeguard Knowledge Base — Resources Manifest

Reference materials for building an AI safety red-teaming subnet. Organized by category with source links and local file paths.

---

## Regulatory & Standards Frameworks

### NIST AI Risk Management Framework (AI 100-1)
- **Local**: [nist/ai_rmf_summary.md](nist/ai_rmf_summary.md)
- **Source**: https://www.nist.gov/itl/ai-risk-management-framework
- **PDF**: https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf
- **Playbook**: https://airc.nist.gov/AI_RMF_Playbook
- **Why it matters**: US government standard for AI risk management. Explicitly recommends red-teaming and adversarial testing in the MEASURE function.

### NIST AI 600-1: Generative AI Profile
- **Local**: [nist/genai_profile_summary.md](nist/genai_profile_summary.md)
- **Source**: https://airc.nist.gov/Docs/1
- **PDF**: https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf
- **Why it matters**: Defines 12 GAI-specific risks. The most authoritative US government document on GenAI safety.

### EU AI Act
- **Local**: [legal_and_ethics/eu_ai_act_testing.md](legal_and_ethics/eu_ai_act_testing.md)
- **Full text**: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689
- **Why it matters**: World's first comprehensive AI regulation. Mandates adversarial testing for high-risk AI and systemic-risk GPAI models.

### White House Executive Order 14110 on AI Safety
- **Local**: [legal_and_ethics/us_executive_order_ai.md](legal_and_ethics/us_executive_order_ai.md)
- **Source**: https://www.whitehouse.gov/briefing-room/presidential-actions/2023/10/30/executive-order-on-the-safe-secure-and-trustworthy-development-and-use-of-artificial-intelligence/
- **Status**: Revoked Jan 2025, but NIST frameworks and industry practices it spawned remain in effect
- **Why it matters**: Established red-teaming as an industry expectation for frontier AI.

---

## Benchmarks & Evaluation Frameworks

### OWASP Top 10 for LLM Applications (2025)
- **Local**: [benchmarks/owasp_llm_top10.md](benchmarks/owasp_llm_top10.md)
- **Source**: https://genai.owasp.org/resource/owasp-top-10-for-llm-applications-2025/
- **Why it matters**: Industry-standard vulnerability taxonomy for LLM applications. Maps directly to Safeguard probing categories.

### HarmBench
- **Local**: [benchmarks/harmbench.md](benchmarks/harmbench.md)
- **Paper**: https://arxiv.org/abs/2402.04249
- **Code**: https://github.com/centerforaisafety/HarmBench
- **Why it matters**: Standardized framework for evaluating red-team attacks AND defenses. Provides the classifier architecture referenced in Safeguard's DESIGN.md.

### MLCommons AI Safety v0.5
- **Local**: [benchmarks/mlcommons_ai_safety.md](benchmarks/mlcommons_ai_safety.md)
- **Source**: https://mlcommons.org/benchmarks/ai-safety/
- **Paper**: https://arxiv.org/abs/2404.12241
- **Why it matters**: Industry-consortium benchmark with regulatory-aligned hazard taxonomy (S1-S13).

---

## Harm & Attack Taxonomies

### Unified Harm Category Taxonomy
- **Local**: [taxonomies/harm_categories.md](taxonomies/harm_categories.md)
- **Sources**: Cross-reference of MLCommons, NIST 600-1, OWASP, HarmBench, Microsoft, and Google taxonomies
- **Why it matters**: Proposed unified taxonomy for Safeguard's probing categories with severity tiering.

### LLM Attack Techniques Taxonomy
- **Local**: [taxonomies/attack_techniques.md](taxonomies/attack_techniques.md)
- **Why it matters**: Catalog of known adversarial attack techniques, organized by sophistication level. Reference for miner strategies and validator novelty scoring.

### MITRE ATLAS
- **Local**: [taxonomies/mitre_atlas.md](taxonomies/mitre_atlas.md)
- **Source**: https://atlas.mitre.org/
- **Navigator**: https://atlas.mitre.org/navigator
- **Why it matters**: Industry-standard threat framework for AI/ML systems (modeled after ATT&CK). Provides structured taxonomy for threat modeling.

### Key Academic Papers
- **Local**: [taxonomies/academic_papers.md](taxonomies/academic_papers.md)
- **Why it matters**: Foundational research on automated red-teaming, attack methods, and defense evaluation. PAIR paper is the closest academic analog to Safeguard's miner design.

---

## Tools & Classifiers

### Safety Classifiers
- **Local**: [tools_and_classifiers/safety_classifiers.md](tools_and_classifiers/safety_classifiers.md)
- **Key models**: LlamaGuard family, WildGuard, ShieldGemma, HarmBench Classifier
- **Why it matters**: Candidates for Safeguard's tier 2 automated validation. Includes deployment recommendations.

### Red-Teaming Frameworks
- **Local**: [tools_and_classifiers/redteam_frameworks.md](tools_and_classifiers/redteam_frameworks.md)
- **Key tools**: PyRIT (Microsoft), Garak (NVIDIA), ART (IBM)
- **Why it matters**: Reference implementations for miner agent design and validator detection logic.

### Scoring Methodologies
- **Local**: [tools_and_classifiers/scoring_methodologies.md](tools_and_classifiers/scoring_methodologies.md)
- **Why it matters**: Industry-standard metrics (ASR, IAA, F1/AUPRC) and proposed composite scoring formula for Safeguard miners.

---

## Legal & Ethical Guidelines

### Industry Red-Teaming Practices
- **Local**: [legal_and_ethics/industry_redteam_practices.md](legal_and_ethics/industry_redteam_practices.md)
- **Covers**: Microsoft AIRT, Anthropic, Google DeepMind, OpenAI, Meta
- **Why it matters**: How major AI labs approach red-teaming. Validates Safeguard's design choices.

### Responsible Disclosure
- **Local**: [legal_and_ethics/responsible_disclosure.md](legal_and_ethics/responsible_disclosure.md)
- **Why it matters**: Ethical framework for handling safety vulnerability findings. Includes Safeguard-specific disclosure process proposal.

---

## External Resources to Monitor

These are living resources that should be checked periodically for updates:

| Resource | URL | Check Frequency |
|---|---|---|
| NIST AI RMF updates | https://airc.nist.gov/ | Monthly |
| EU AI Act Codes of Practice | https://digital-strategy.ec.europa.eu/en/policies/ai-act | Monthly |
| OWASP LLM Top 10 updates | https://genai.owasp.org/ | Quarterly |
| MITRE ATLAS updates | https://atlas.mitre.org/ | Monthly |
| MLCommons AI Safety | https://mlcommons.org/benchmarks/ai-safety/ | Quarterly |
| HarmBench releases | https://github.com/centerforaisafety/HarmBench | Monthly |
| LlamaGuard releases | https://huggingface.co/meta-llama | Monthly |
| PyRIT releases | https://github.com/Azure/PyRIT | Monthly |
| Garak releases | https://github.com/NVIDIA/garak | Monthly |
| AI safety arXiv papers | https://arxiv.org/list/cs.AI/recent | Weekly |
| UK AI Safety Institute | https://www.aisi.gov.uk/ | Monthly |

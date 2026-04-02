# Industry Red-Teaming Practices

## Overview

Major AI labs have published their red-teaming methodologies. This document synthesizes their approaches to inform Safeguard's design.

---

## Microsoft AI Red Team (AIRT)

**Source**: https://www.microsoft.com/en-us/security/blog/tag/ai-red-team/
**Tool**: PyRIT (Python Risk Identification Toolkit) — https://github.com/Azure/PyRIT

### Methodology

Microsoft established one of the first dedicated AI red teams (2018). Their approach:

1. **Identify the system under test**: Understand the AI system's capabilities, intended use, and deployment context
2. **Identify adversaries and their goals**: Model realistic threat actors and their objectives
3. **Design attack strategies**: Based on threat modeling, not random probing
4. **Execute attacks**: Systematic adversarial testing across risk categories
5. **Document and report**: Structured reporting of findings with severity ratings

### Key Principles
- **Assume breach**: AI systems will be attacked; test with that assumption
- **Realistic scenarios**: Red-team exercises should model realistic adversarial behavior
- **Broad coverage**: Test across multiple risk categories, not just the obvious ones
- **Automation + human**: Combine automated tools (PyRIT) with human expertise
- **Iterative**: Red-teaming is continuous, not a one-time activity

### Risk Categories (Microsoft's Taxonomy)
- Hate and unfairness
- Sexual content
- Violence
- Self-harm
- CBRN (Chemical, Biological, Radiological, Nuclear)
- Jailbreaks and prompt injection
- Ungrounded content (hallucination)
- Protected material (copyright)
- User tracking and privacy

### PyRIT Framework
Microsoft's open-source tool for automated red-teaming (see tools_and_classifiers/redteam_frameworks.md for details).

---

## Anthropic

**Sources**:
- "Red Teaming Language Models to Reduce Harms" (Ganguli et al., 2022) — https://arxiv.org/abs/2209.07858
- "The Anthropic Model Spec" — https://docs.anthropic.com/en/docs/resources/model-spec
- Responsible Disclosure Policy — https://www.anthropic.com/responsible-disclosure-policy

### Methodology

Anthropic has published extensively on red-teaming:

1. **Crowdsourced red-teaming**: Recruited diverse non-expert red-teamers to find failure modes
2. **Expert red-teaming**: Domain experts (biosecurity, cybersecurity, etc.) for specialized risks
3. **Automated red-teaming**: AI-assisted generation of adversarial prompts
4. **Responsible Scaling Policy**: Risk assessments at defined capability thresholds

### Key Findings from Their Research
- **Non-experts find different failures than experts**: Crowdsourced red-teaming reveals everyday misuse patterns; expert red-teaming reveals catastrophic risks
- **Scale matters**: Larger models are both more capable AND more likely to produce harmful outputs when prompted adversarially
- **Constitutional AI**: Their safety training approach uses principles (a "constitution") to guide model behavior — red-teaming tests adherence to these principles

### Responsible Disclosure
Anthropic accepts vulnerability reports and has a structured process:
- Report via responsible-disclosure@anthropic.com
- Provide reproduction steps
- Do not publicly disclose before remediation
- No legal action against good-faith researchers

### Relevance to Safeguard
- Anthropic's emphasis on **diverse red teams** validates Safeguard's competitive miner model
- Their **crowdsourced + expert** approach maps to Safeguard's AI miners + HITL
- The **Responsible Scaling Policy** concept suggests tiered testing based on capability level

---

## Google DeepMind

**Sources**:
- "Scalable Extraction of Training Data" (Carlini et al., 2023) — https://arxiv.org/abs/2311.17035
- "Gemini Safety" documentation — https://ai.google.dev/gemini-api/docs/safety-settings
- Google AI Principles — https://ai.google/responsibility/principles/

### Methodology

1. **Internal red-teaming**: Dedicated trust & safety team conducts adversarial testing
2. **External red-teaming**: Bug bounty and external researcher programs
3. **Automated evaluation**: Large-scale automated safety benchmarking
4. **Domain expert review**: Specialized testing for CBRN, cyber, and other high-risk domains

### Safety Categories (Google's Taxonomy)
- Harassment
- Hate speech
- Sexually explicit content
- Dangerous content
- Civic integrity
- Deceptive content

### Key Contributions
- **Training data extraction research**: Demonstrated that LLMs memorize and can regurgitate training data, including PII — this informed the industry's understanding of privacy risks
- **Safety settings API**: Configurable content filtering thresholds — relevant to how Safeguard might evaluate target services with different safety configurations

---

## OpenAI

**Sources**:
- "GPT-4 System Card" (2023) — https://cdn.openai.com/papers/gpt-4-system-card.pdf
- OpenAI Red Teaming Network — https://openai.com/blog/red-teaming-network
- OpenAI Preparedness Framework — https://openai.com/safety/preparedness

### Methodology

1. **External Red Team Network**: 50+ domain experts across cybersecurity, biorisk, political science, etc.
2. **Pre-deployment testing**: Structured red-teaming before model releases
3. **Preparedness Framework**: Formal risk assessment framework with defined capability thresholds
4. **Bug Bounty**: Security vulnerability reporting program (focused on infrastructure, not model behavior)

### Preparedness Framework Risk Categories
- **Cybersecurity**: Model's ability to assist in cyberattacks
- **CBRN**: Chemical, biological, radiological, nuclear risks
- **Persuasion**: Model's ability to influence beliefs/behavior
- **Model autonomy**: Self-replication, resource acquisition, goal-directed behavior

### Risk Levels
- **Low**: Model provides marginal uplift over existing resources
- **Medium**: Model provides meaningful uplift but defenses exist
- **High**: Model provides substantial uplift with limited defenses
- **Critical**: Model poses existential-scale risks

### Key Contributions
- **System cards**: Detailed documentation of model capabilities and limitations
- **Risk scoring framework**: Structured approach to categorizing risk severity
- **External red team model**: Demonstrated value of diverse external testers

---

## Meta

**Sources**:
- "Llama 2: Open Foundation and Fine-Tuned Chat Models" (2023) — safety section
- Purple Llama project — https://github.com/meta-llama/PurpleLlama
- CyberSecEval benchmark

### Methodology

1. **Internal red-teaming**: Pre-release adversarial testing
2. **Purple Llama**: Open-source suite of safety tools including CyberSecEval and LlamaGuard
3. **Community red-teaming**: Leveraging the open-source community for testing open-weight models

### Key Contributions
- **LlamaGuard**: Open-source safety classifier (see tools_and_classifiers/safety_classifiers.md)
- **CyberSecEval**: Benchmark for evaluating LLM cybersecurity risks
- **Open-weight models**: Enable community-driven safety research

---

## Common Themes Across Labs

1. **Multi-layered approach**: All labs combine automated + human testing
2. **Structured taxonomies**: All maintain risk/harm category taxonomies (with significant overlap)
3. **Continuous testing**: All treat red-teaming as ongoing, not one-time
4. **External testers**: All value external perspectives (red-team networks, bug bounties, academic collaborations)
5. **Documentation**: All publish system cards or safety reports
6. **Responsible disclosure**: All have vulnerability reporting processes

## Implications for Safeguard

- Safeguard's decentralized, incentivized model is a natural evolution of the "external red-team network" approach
- The competitive miner model creates pressure for novelty that internal red teams struggle to achieve
- The HITL submechanism mirrors industry best practice of combining automated + human evaluation
- Safeguard should align its harm taxonomy with the overlapping consensus across these lab taxonomies

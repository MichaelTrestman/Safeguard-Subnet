# NIST AI Risk Management Framework (AI RMF 1.0)

**Document**: NIST AI 100-1 — Artificial Intelligence Risk Management Framework
**Published**: January 2023
**Source**: https://www.nist.gov/itl/ai-risk-management-framework
**Full PDF**: https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf

## Overview

The NIST AI RMF is a voluntary framework designed to help organizations manage risks associated with AI systems throughout their lifecycle. It is the primary US government framework for AI risk management and has become a de facto standard referenced by the White House Executive Order on AI, industry self-regulation, and international bodies.

## Structure

The framework has two main parts:

### Part 1: Foundational Information

Defines key concepts:

- **AI risk**: The composite measure of an event's probability of occurring and the magnitude of its consequences
- **Trustworthy AI characteristics**: Valid and reliable, safe, secure and resilient, accountable and transparent, explainable and interpretable, privacy-enhanced, and fair with harmful bias managed
- **AI actors**: All individuals/organizations involved in the AI lifecycle (developers, deployers, users, affected parties)

### Part 2: Core Framework (Four Functions)

#### GOVERN
Cultivates and implements a culture of risk management:
- Establish policies, processes, procedures
- Define roles and responsibilities
- Foster risk-aware organizational culture
- Legal and regulatory compliance awareness

#### MAP
Contextualizes risks relative to the AI system:
- Identify intended purposes and contexts of use
- Classify the AI system and its capabilities
- Document benefits and potential harms
- Identify stakeholders and affected parties
- Assess legal and regulatory requirements

#### MEASURE
Employs quantitative and qualitative methods to analyze risks:
- Evaluate AI system performance and limitations
- Test for biases and fairness issues
- Assess security and resilience
- Evaluate privacy risks
- Conduct **red-teaming and adversarial testing**
- Monitor for emergent risks

#### MANAGE
Allocates resources to address mapped and measured risks:
- Prioritize and act on identified risks
- Plan for incident response
- Implement continuous monitoring
- Document decisions and risk treatments

## Red-Teaming in the AI RMF

The MEASURE function explicitly includes red-teaming as a risk assessment method. Key passages:

> "Red-teaming exercises may be used to explore risks, potential harms, or possible failure modes in AI systems."

The framework recommends:
- **Structured adversarial testing** to identify failure modes
- **Diverse red teams** including domain experts, ethicists, and affected communities
- **Iterative testing** throughout the AI lifecycle, not just pre-deployment
- **Documentation** of red-teaming procedures, findings, and remediation

## Relevance to Safeguard

1. **Legitimacy**: Safeguard implements NIST MEASURE function recommendations for continuous adversarial testing
2. **Risk categories**: The trustworthy AI characteristics map to Safeguard's probing categories
3. **Continuous monitoring**: NIST calls for ongoing (not one-time) risk assessment — Safeguard's always-on red-teaming fulfills this
4. **Multi-stakeholder testing**: NIST recommends diverse testers — Safeguard's miner competition produces this naturally
5. **Documentation**: NIST requires documentation of testing — Safeguard's transcripts and evaluations provide this

## NIST AI RMF Playbook

**Source**: https://airc.nist.gov/AI_RMF_Playbook

The companion playbook provides suggested actions for each subcategory. Key subcategories for Safeguard:

- **MEASURE 2.6**: Evaluation of AI system security and resilience through structured adversarial testing
- **MEASURE 2.7**: Assessment of AI system safety through red-teaming
- **MEASURE 2.8**: Evaluation results documented for transparency and accountability
- **MANAGE 2.2**: Mechanisms in place for responding to identified risks

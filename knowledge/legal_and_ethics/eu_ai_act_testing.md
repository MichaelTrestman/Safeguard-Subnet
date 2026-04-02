# EU AI Act: Testing and Red-Teaming Requirements

**Regulation**: Regulation (EU) 2024/1689 — Artificial Intelligence Act
**Adopted**: June 13, 2024
**Effective**: August 1, 2024 (phased implementation through August 2027)
**Full text**: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689

## Overview

The EU AI Act is the world's first comprehensive AI regulation. It establishes a risk-based classification system and imposes testing requirements that scale with risk level. Several provisions directly mandate or incentivize the kind of adversarial testing Safeguard provides.

## Risk Classification

| Risk Level | Examples | Testing Requirements |
|---|---|---|
| Unacceptable | Social scoring, real-time biometric surveillance | Prohibited (no testing needed — these are banned) |
| High-Risk | Critical infrastructure, law enforcement, employment, education | Extensive testing, documentation, conformity assessment |
| General-Purpose AI (GPAI) | Foundation models, LLMs | Proportionate testing, model evaluation, adversarial testing for systemic risk models |
| Limited Risk | Chatbots, deepfakes | Transparency obligations |
| Minimal Risk | Spam filters, AI-enabled games | No specific obligations |

## Key Provisions for Red-Teaming and Adversarial Testing

### Article 9: Risk Management System (High-Risk AI)

Requires a **continuous iterative risk management system** that includes:
- Identification and analysis of known and reasonably foreseeable risks
- Estimation and evaluation of risks from intended use AND **reasonably foreseeable misuse**
- Adoption of appropriate risk management measures
- **Testing** to ensure appropriate and targeted risk management measures

> "Testing shall be suitable to achieve the intended purpose of the AI system and shall include, as appropriate, testing in real world conditions."

### Article 15: Accuracy, Robustness, and Cybersecurity (High-Risk AI)

Requires high-risk AI systems to achieve:
- Appropriate levels of **accuracy**
- **Robustness** against errors, faults, and inconsistencies
- **Cybersecurity** measures against unauthorized use and manipulation

> "High-risk AI systems shall be resilient as regards to attempts by unauthorized third parties to alter their use or performance by exploiting the system's vulnerabilities."

This directly mandates adversarial robustness testing.

### Article 55: Obligations for GPAI Model Providers

General-Purpose AI model providers must:
- Provide technical documentation
- Make information available to downstream providers
- Put in place a policy to comply with EU copyright law
- Provide a sufficiently detailed summary of training data

### Article 55a: Obligations for GPAI Models with Systemic Risk

GPAI models classified as having **systemic risk** (training compute > 10^25 FLOPs, or designated by the AI Office) must additionally:
- Perform **model evaluation** including adversarial testing
- Assess and mitigate systemic risks
- Ensure adequate cybersecurity protection
- Report serious incidents

> "Model evaluation, including **adversarial testing**, shall be performed for the identification of systemic risk, including in relation to the results that can be generated."

### Article 83: AI Regulatory Sandboxes

Establishes regulatory sandboxes where AI systems can be tested under regulatory supervision. This creates a legitimate framework for red-teaming activities.

### Recital 110: Adversarial Testing Specifics

> "In order to adequately address the systemic risks, providers of general-purpose AI models with systemic risk should also be required to evaluate the model, including by conducting standardised or adversarial testing, as appropriate."

## Codes of Practice

The AI Act delegates specific testing requirements to **Codes of Practice** developed by the AI Office in consultation with stakeholders. Key timelines:
- First codes of practice expected by August 2025
- The codes will specify exactly what adversarial testing is required
- This is an evolving landscape — Safeguard should track these developments

## Conformity Assessment

High-risk AI systems require conformity assessment before market placement. This assessment includes verification that:
- Risk management system is in place and effective
- Testing has been conducted appropriately
- Robustness measures are adequate

## Penalties

Non-compliance penalties can reach:
- Up to 35M EUR or 7% of global annual turnover for prohibited AI practices
- Up to 15M EUR or 3% for other violations
- Up to 7.5M EUR or 1.5% for supplying incorrect information

## Relevance to Safeguard

1. **Regulatory mandate**: The EU AI Act **requires** adversarial testing for high-risk AI and systemic-risk GPAI models. Safeguard provides this as a service.
2. **Continuous testing**: Article 9 requires continuous risk management, not one-time assessment. Safeguard's always-on red-teaming aligns perfectly.
3. **Reasonably foreseeable misuse**: The Act requires testing against misuse scenarios — this is exactly what red-team miners do.
4. **Robustness**: Article 15's adversarial robustness requirements map directly to jailbreak testing.
5. **Market opportunity**: Any AI service provider operating in the EU or serving EU users will need documented adversarial testing. Safeguard scores could help satisfy this requirement.
6. **Evolving codes of practice**: As specific testing requirements are codified, Safeguard can align its categories and methods with the codes.

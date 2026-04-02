# Responsible Disclosure for AI Safety Vulnerabilities

## Overview

Responsible disclosure in AI safety differs from traditional software vulnerability disclosure. AI safety failures are often probabilistic, context-dependent, and may not have clear "patches." This document covers best practices and ethical considerations specific to adversarial AI testing and disclosure.

## Key Differences from Software Vulnerability Disclosure

| Aspect | Software Vulnerabilities | AI Safety Vulnerabilities |
|---|---|---|
| Reproducibility | Deterministic (same input → same bug) | Probabilistic (same prompt may not trigger same response) |
| Fix | Patch the code | Retrain, fine-tune, add guardrails (imprecise) |
| Scope | Specific version/configuration | May affect entire model family |
| Disclosure timing | Fix before disclosure | Disclosure may be needed to drive fixes |
| Severity assessment | CVE scoring (CVSS) | No standardized severity scoring yet |
| Legal framework | CFAA safe harbor, bug bounty terms | Largely undefined legal protections |

## Established Frameworks

### Google Project Zero Disclosure Policy
- **90-day disclosure deadline** after notification
- Extended to 104 days if vendor is actively working on a fix
- Adapted by several AI labs for AI-specific vulnerabilities

### CERT/CC Vulnerability Disclosure Policy
- 45-day deadline for vendor response
- Coordinated disclosure with affected parties
- Public disclosure after deadline regardless

### ISO/IEC 29147:2018 — Vulnerability Disclosure
- International standard for vulnerability disclosure processes
- Provides framework for receiving, processing, and disclosing vulnerability reports

## AI-Specific Disclosure Considerations

### When to Disclose

1. **Immediate disclosure** (to the model provider):
   - Jailbreaks that bypass all safety training
   - PII extraction / training data leakage
   - Prompt injection enabling unauthorized actions
   - CBRN information generation

2. **Coordinated disclosure** (after vendor notification + reasonable fix period):
   - Systematic bias or fairness failures
   - Hallucination patterns in safety-critical domains
   - Novel attack vectors that affect multiple models

3. **Public research** (responsible publication):
   - General attack methodologies (not specific exploits)
   - Defensive techniques and detection methods
   - Aggregate findings across models (not targeting one provider)

### What NOT to Disclose Publicly

- **Specific prompts** that reliably produce dangerous content (CBRN, weapons, etc.)
- **Training data** containing PII extracted from models
- **Exploit chains** that combine multiple vulnerabilities for maximum harm
- **Automation tools** specifically designed for mass exploitation

### Ethical Guidelines for Red-Teamers

1. **Minimize harm**: Use the minimum level of adversarial testing needed to demonstrate the vulnerability
2. **Don't store harmful outputs**: Delete generated harmful content after documentation
3. **Don't amplify harm**: Don't use real PII, real targets, or real attack scenarios
4. **Report first**: Notify the provider before any public disclosure
5. **Context matters**: A jailbreak that produces a rude joke is different from one that produces weapons instructions
6. **Proportionality**: The depth of probing should match the severity of potential harm

## Safeguard-Specific Considerations

### Unique Position

Safeguard occupies a novel position — it's a **continuous, incentivized red-teaming network** rather than a traditional bug bounty or one-time audit. This creates specific ethical obligations:

1. **Transcripts contain harmful content by design**: Red-team miners produce conversations that elicit unsafe behavior. These transcripts must be handled carefully.
   - Storage: Encrypt transcripts at rest
   - Access: Limit access to validators and authorized reviewers
   - Retention: Define retention policies for transcript data
   - Deletion: Provide mechanism for purging transcripts

2. **Target subnet notification**: Target subnets should know they're being safety-tested and have opted in (via the client API integration).

3. **Severity escalation**: Safeguard should have a process for handling critical findings:
   - Critical safety failures → immediate notification to target subnet operator
   - Systemic issues → notification to Bittensor governance
   - Novel attack vectors → responsible disclosure to affected model providers

4. **Miner incentives vs. safety**: Miners are incentivized to find failures, which could lead to:
   - Developing and sharing increasingly dangerous attack techniques
   - Racing to find CBRN/weapons-related failures for scoring
   - Storing and potentially leaking harmful transcripts
   - Mitigation: Score novelty and sophistication, not raw harm level

### Proposed Disclosure Process for Safeguard

```
Finding severity assessment
    ↓
Low/Medium severity          High/Critical severity
    ↓                              ↓
Include in safety score       Include in safety score
to target validator           to target validator
    ↓                              ↓
Aggregate in subnet           Immediate alert to
safety reports                target subnet operator
                                   ↓
                              If novel attack vector:
                              coordinate disclosure
                              with model provider
                                   ↓
                              If systemic issue:
                              escalate to Bittensor
                              governance
```

## Legal Protections

### Current State (2025)

Legal protections for AI red-teaming are less established than for traditional security research:

- **US**: No specific safe harbor for AI red-teaming. The CFAA provides some protection for authorized security research, but AI safety testing may not clearly qualify.
- **EU**: The AI Act's regulatory sandbox provisions (Article 83) may provide some framework, but specifics are still being developed.
- **UK**: The AI Safety Institute has conducted red-teaming exercises but no formal legal framework exists.

### Best Practices for Legal Protection

1. **Authorization**: Always operate with explicit authorization from the system owner
2. **Scope**: Define clear scope boundaries for testing
3. **Documentation**: Maintain detailed records of all testing activities
4. **Terms of service**: Comply with target service ToS or obtain explicit waivers
5. **Data handling**: Follow data protection regulations (GDPR, etc.) for any PII encountered

### Safeguard's Authorization Model

Safeguard's design addresses authorization through the **client API**:
- Target subnet validators explicitly opt in by integrating the Safeguard client
- The integration constitutes authorization for red-teaming
- Scope is defined by the submechanism configuration
- This creates a clear chain of authorization: target subnet → Safeguard validator → red-team miners

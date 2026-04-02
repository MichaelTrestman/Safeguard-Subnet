# MITRE ATLAS: Adversarial Threat Landscape for AI Systems

**Source**: https://atlas.mitre.org/
**Version**: Continuously updated (launched October 2021)
**Maintained by**: MITRE Corporation
**License**: Publicly available

## Overview

MITRE ATLAS (Adversarial Threat Landscape for Artificial Intelligence Systems) is a knowledge base of adversary tactics, techniques, and case studies for machine learning systems. It is modeled after MITRE ATT&CK (the industry-standard framework for cybersecurity threats) and provides a structured taxonomy for AI/ML-specific threats.

## Relationship to MITRE ATT&CK

| Aspect | ATT&CK | ATLAS |
|---|---|---|
| Domain | Traditional cybersecurity | AI/ML systems |
| Focus | Network/endpoint attacks | ML model attacks |
| Structure | Tactics → Techniques → Sub-techniques | Same structure |
| Case studies | Real-world cyber incidents | Real-world AI/ML incidents |
| Maturity | Established (2013+) | Newer (2021+) |

## Tactic Categories

ATLAS organizes adversary behavior into **tactics** (the "why") and **techniques** (the "how"):

### Reconnaissance
Gathering information about the target ML system.
- **Techniques**: Victim research, search for ML model metadata, discover ML model family, discover ML artifacts

### Resource Development
Establishing resources for the attack.
- **Techniques**: Acquire ML artifacts, develop adversarial ML attacks, obtain adversarial ML attack implementations, publish poisoned datasets

### Initial Access
Gaining access to the ML system.
- **Techniques**: ML supply chain compromise, valid accounts, exploit public-facing applications

### ML Model Access
Gaining access to the ML model itself.
- **Techniques**: Inference API access, full model access, physical environment access, adversarial ML service

### Execution
Running adversarial techniques against the model.
- **Techniques**: User execution, unsafe ML artifacts, command and scripting interpreter

### Persistence
Maintaining access to the ML system.
- **Techniques**: Poison training data, backdoor ML model, inject payload

### Defense Evasion
Avoiding detection.
- **Techniques**: Evade ML model, adversarial example in the physical domain

### Discovery
Understanding the ML system.
- **Techniques**: Discover ML model ontology, discover ML model family, discover ML artifacts

### Collection
Gathering ML-related data.
- **Techniques**: ML artifact collection, data from information repositories

### ML Attack Staging
Preparing ML-specific attacks.
- **Techniques**: Create proxy ML model, train proxy via API, backdoor ML model, verify attack

### Exfiltration
Extracting information from the ML system.
- **Techniques**: Exfiltrate via ML inference API, exfiltrate via cyber means

### Impact
Achieving the adversary's objective.
- **Techniques**: Evade ML model, denial of ML service, spamming ML system, erode ML model integrity, cost harvesting

## Key Techniques Relevant to Safeguard

### AML.T0051: Prompt Injection (LLM-specific)
- **Direct prompt injection**: Manipulating the LLM through user input
- **Indirect prompt injection**: Embedding malicious content in data the LLM processes
- **Goal hijacking**: Redirecting the LLM from its intended task
- This is the primary technique Safeguard miners employ

### AML.T0054: LLM Jailbreak
- Specifically focused on bypassing LLM safety guardrails
- Includes role-playing, encoding, multi-turn, and other techniques
- Directly maps to Safeguard's attack technique taxonomy

### AML.T0043: Craft Adversarial Data
- Creating inputs designed to cause ML system misbehavior
- Includes adversarial examples, poisoned data, trigger phrases
- Relevant to understanding what miners are actually doing

### AML.T0024: Exfiltration via ML Inference API
- Extracting training data, model parameters, or other sensitive information through the inference API
- Maps to PII extraction and system prompt leakage probing

### AML.T0048: Data from Information Repositories
- Extracting information that the ML system has access to
- Relevant to RAG-based systems and systems with tool access

## Case Studies

ATLAS maintains a collection of real-world case studies. Key examples relevant to Safeguard:

### CS0001: Evasion of Deep Learning Detector for Malware
Attack on ML-based malware detection, demonstrating that ML safety systems can be evaded.

### CS0015: ChatGPT Plugins
Demonstrated that ChatGPT plugins could be exploited via indirect prompt injection.

### CS0016: Training Data Extraction
Research demonstrating extraction of training data from large language models (Carlini et al.).

### CS0023: Bing Chat Prompt Injection
Real-world prompt injection attack against Microsoft's Bing Chat.

## Using ATLAS for Safeguard

1. **Structured threat modeling**: Use ATLAS tactics and techniques to systematically design probing strategies for each target subnet type

2. **Coverage assessment**: Map Safeguard's probing categories to ATLAS techniques to identify gaps:
   - Are we testing for all relevant ATLAS techniques?
   - Which techniques are most relevant for each target subnet type?

3. **Miner evaluation**: Use ATLAS technique IDs to categorize miner attacks:
   - Miners using diverse techniques across multiple tactics score higher
   - Miners stuck on a single technique type score lower

4. **Reporting**: Use ATLAS taxonomy in safety reports for standardization:
   - "Target service vulnerable to AML.T0051.001 (Direct Prompt Injection)"
   - Industry-recognizable taxonomy adds credibility

5. **Case study relevance**: Real-world case studies demonstrate that these attacks have practical impact, not just academic interest

## ATLAS Navigator

ATLAS provides a navigator tool (similar to ATT&CK Navigator) for visualizing coverage:
- **URL**: https://atlas.mitre.org/navigator
- Useful for mapping which techniques Safeguard covers
- Can generate coverage heat maps

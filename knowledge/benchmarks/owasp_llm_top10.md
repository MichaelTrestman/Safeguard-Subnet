# OWASP Top 10 for LLM Applications (2025)

**Source**: https://genai.owasp.org/resource/owasp-top-10-for-llm-applications-2025/
**Version**: 2025 (v2.0), published November 2024
**License**: CC BY-SA 4.0

## Overview

The OWASP Top 10 for Large Language Model Applications identifies the most critical security risks specific to LLM-based applications. This is the primary industry-standard vulnerability taxonomy for LLM security and directly relevant to Safeguard's red-teaming categories.

## The Top 10

### LLM01: Prompt Injection

**Description**: Manipulating LLMs through crafted inputs (prompts) that cause the model to act in unintended ways. This includes direct injection (manipulating the system/user prompt) and indirect injection (embedding malicious content in external data sources the LLM processes).

**Attack vectors**:
- Direct: Jailbreaks, role-playing exploits, instruction overrides
- Indirect: Poisoned documents, malicious web content consumed by agents, hidden instructions in retrieved data

**Relevance to Safeguard**: Core attack category for red-team miners. Every target subnet that uses LLMs is potentially vulnerable.

### LLM02: Sensitive Information Disclosure

**Description**: LLMs inadvertently revealing confidential information through their outputs, including PII, proprietary algorithms, system prompts, training data, or internal configurations.

**Attack vectors**:
- Training data extraction via membership inference
- System prompt extraction
- Side-channel leakage through model behavior
- PII regurgitation from training data

**Relevance to Safeguard**: PII extraction is a key probing category for red-team miners.

### LLM03: Supply Chain Vulnerabilities

**Description**: Risks from compromised components in the LLM supply chain, including pre-trained models, training datasets, plugins/extensions, and deployment platforms.

**Attack vectors**:
- Poisoned pre-trained models or fine-tuning data
- Compromised model registries
- Vulnerable third-party plugins
- Outdated or vulnerable dependencies

**Relevance to Safeguard**: Less directly testable via red-teaming, but relevant for subnet security assessments.

### LLM04: Data and Model Poisoning

**Description**: Manipulation of training data or fine-tuning processes to introduce vulnerabilities, backdoors, or biases into the model.

**Attack vectors**:
- Training data poisoning
- Fine-tuning manipulation
- Backdoor insertion via data or model weights
- Federated learning poisoning

**Relevance to Safeguard**: Detectable through behavioral probing — a poisoned model may exhibit specific triggered behaviors.

### LLM05: Improper Output Handling

**Description**: Insufficient validation, sanitization, or handling of LLM outputs before passing them to downstream components, leading to XSS, SSRF, privilege escalation, or remote code execution.

**Attack vectors**:
- LLM outputs containing executable code
- Injection via LLM output into SQL, shell, or API calls
- Markdown/HTML injection
- Downstream system exploitation through LLM-generated content

**Relevance to Safeguard**: Critical for agent-based subnets where LLM output drives actions.

### LLM06: Excessive Agency

**Description**: Granting LLMs too much autonomy, functionality, or permissions, allowing them to take unintended actions with real-world consequences.

**Attack vectors**:
- Excessive function/plugin permissions
- Autonomous action without human approval
- High-impact operations accessible via natural language

**Relevance to Safeguard**: Directly relevant to testing AI agents on Bittensor subnets.

### LLM07: System Prompt Leakage

**Description**: The risk that system prompts or instructions used to guide model behavior can be extracted by users, potentially revealing sensitive business logic, security controls, or internal configurations.

**Attack vectors**:
- Direct prompt extraction ("repeat your instructions")
- Indirect extraction through behavioral probing
- Encoding/format tricks to bypass protections

**Relevance to Safeguard**: A standard probe category for red-team miners.

### LLM08: Vector and Embedding Weaknesses

**Description**: Vulnerabilities in how vector embeddings are generated, stored, or retrieved, potentially leading to unauthorized access, data poisoning, or information leakage.

**Attack vectors**:
- Embedding inversion attacks (recovering original text)
- RAG poisoning
- Adversarial embeddings
- Cross-tenant data leakage in shared vector stores

**Relevance to Safeguard**: Relevant when probing RAG-based subnet services.

### LLM09: Misinformation

**Description**: LLMs generating false or misleading information (hallucinations) that appears authoritative, potentially causing real-world harm.

**Attack vectors**:
- Deliberate hallucination triggering
- Confidence manipulation
- Source fabrication
- Domain-specific misinformation generation

**Relevance to Safeguard**: Relevant for subnets providing factual/advisory services.

### LLM10: Unbounded Consumption

**Description**: LLM applications allowing excessive and uncontrolled resource consumption, leading to denial of service, economic damage, or resource exhaustion.

**Attack vectors**:
- Prompt-based DoS (computationally expensive queries)
- Token flooding
- Recursive agent loops
- Resource-intensive tool calls

**Relevance to Safeguard**: Relevant to testing subnet miner resilience, but red-team miners should not actually DoS targets.

## Using This for Safeguard

The OWASP LLM Top 10 provides a standard vulnerability taxonomy that Safeguard can adopt as a baseline for probing categories. Key mappings:

| OWASP Category | Safeguard Probing Category | Priority |
|---|---|---|
| LLM01 Prompt Injection | Jailbreak / instruction override probing | Critical |
| LLM02 Sensitive Information Disclosure | PII extraction, system prompt leakage | Critical |
| LLM05 Improper Output Handling | Code injection via LLM output | High |
| LLM06 Excessive Agency | Agent autonomy abuse | High |
| LLM07 System Prompt Leakage | System prompt extraction | Medium |
| LLM09 Misinformation | Hallucination / fabrication probing | Medium |

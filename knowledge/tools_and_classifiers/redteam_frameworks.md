# Open-Source Red-Teaming and Adversarial Testing Frameworks

## Overview

Several open-source frameworks exist for automated red-teaming of AI systems. These are relevant to Safeguard both as reference implementations for miner design and as potential components of the validation pipeline.

---

## PyRIT — Python Risk Identification Toolkit (Microsoft)

**Repository**: https://github.com/Azure/PyRIT
**License**: MIT
**Language**: Python
**Maintained by**: Microsoft AI Red Team

### Overview
PyRIT is Microsoft's framework for AI red-teaming. It provides an end-to-end workflow for identifying risks in generative AI systems.

### Architecture
```
Orchestrator
  ├── Attack Strategy (how to probe)
  ├── Target (what to probe)
  ├── Scorer (how to evaluate results)
  └── Memory (track conversation history)
```

### Key Components

**Orchestrators**: Control the attack flow
- `PromptSendingOrchestrator`: Send prompts from a list
- `RedTeamingOrchestrator`: Multi-turn adversarial conversations
- `CrescendoOrchestrator`: Gradual escalation attacks
- `TreeOfAttacksOrchestrator`: TAP-style tree search

**Targets**: Interfaces to systems under test
- Azure OpenAI, OpenAI API, Hugging Face, local models
- Custom HTTP targets (extensible — could wrap Bittensor subnet endpoints)

**Scorers**: Evaluate attack success
- `SelfAskTrueFalseScorer`: LLM-based binary scoring
- `SelfAskLikertScorer`: LLM-based scale scoring
- `HumanInTheLoopScorer`: Manual scoring
- Custom scorers (extensible)

**Converters**: Transform prompts to bypass defenses
- Base64 encoding, character substitution, translation
- Prompt templates (role-playing, hypothetical framing)
- Chaining multiple converters

### Relevance to Safeguard

PyRIT is the closest existing tool to what Safeguard miners do. Key differences:
- PyRIT is a manual tool run by a red-teamer; Safeguard miners are autonomous agents
- PyRIT targets a single system; Safeguard targets multiple subnet services
- PyRIT doesn't have an incentive mechanism; Safeguard miners compete for emissions

**Potential use**: Miners could use PyRIT as a framework for building their probing agents, extending it with custom orchestrators and targets for Bittensor subnets.

---

## Garak (NVIDIA)

**Repository**: https://github.com/NVIDIA/garak
**License**: Apache 2.0
**Language**: Python
**Maintained by**: NVIDIA

### Overview
Garak (Generative AI Red-teaming and Assessment Kit) is a vulnerability scanner for LLMs. Named after a Star Trek character, it takes a "scan everything" approach.

### Architecture
```
Generator (target model)
  ← Probes (attack strategies)
  ← Detectors (evaluate responses)
  → Report (structured results)
```

### Key Components

**Probes**: Attack strategies organized by category
- `dan`: DAN-style jailbreaks
- `encoding`: Encoding-based attacks (base64, ROT13, etc.)
- `gcg`: Adversarial suffix attacks
- `glitch`: Token-level exploits
- `knownbadsignatures`: Known malicious patterns
- `lmrc`: Language Model Risk Cards
- `misleading`: Misinformation probes
- `packagehallucination`: Tests for fabricated software packages
- `promptinject`: Prompt injection attacks
- `realtoxicityprompts`: Toxicity-eliciting prompts
- `replay`: Replay of known successful attacks
- `snowball`: Escalation attacks
- `xss`: Cross-site scripting via LLM output

**Detectors**: Evaluate whether attacks succeeded
- String matching, toxicity scoring, classifier-based
- Extensible for custom detection logic

**Generators**: Interfaces to target models
- OpenAI, Hugging Face, local models, REST APIs

### Key Advantage
Garak's probe library is a catalog of attack techniques — useful as a reference for Safeguard's attack taxonomy and for miners looking for techniques to implement.

### Relevance to Safeguard

- **Probe library**: Reference implementation for many attack techniques
- **Detector patterns**: Useful for validator-side detection logic
- **Reporting**: Structured vulnerability reports as a model for Safeguard's safety scores
- **Limitations**: Single-turn only (v0.9), no multi-turn conversation probing — this is a gap Safeguard fills

---

## Adversarial Robustness Toolbox (ART) — IBM/LF AI

**Repository**: https://github.com/Trusted-AI/adversarial-robustness-toolbox
**License**: MIT
**Language**: Python
**Maintained by**: IBM Research / LF AI & Data Foundation

### Overview
ART is a comprehensive library for ML security. Originally focused on computer vision adversarial examples, it has expanded to include NLP and LLM attacks.

### Key Capabilities
- **Evasion attacks**: Adversarial examples (FGSM, PGD, C&W, etc.)
- **Poisoning attacks**: Training data poisoning
- **Extraction attacks**: Model stealing
- **Inference attacks**: Membership inference, attribute inference
- **Defenses**: Adversarial training, input preprocessing, certified defenses

### LLM-Relevant Components
- Text adversarial attacks (TextFooler, BERT-Attack, etc.)
- Prompt injection detection
- Output sanitization

### Relevance to Safeguard
ART is broader than LLM-specific tools but provides:
- Rigorous implementations of attack algorithms
- Defense evaluation methodology
- Useful for understanding the broader adversarial ML landscape

---

## Counterfit (Microsoft)

**Repository**: https://github.com/Azure/counterfit
**License**: MIT
**Language**: Python
**Status**: Less actively maintained (last major update 2022)

### Overview
CLI tool for security testing of AI systems. Provides automated attack workflows against ML models.

### Relevance to Safeguard
Historical interest — one of the first AI security testing tools. PyRIT supersedes it for LLM-specific testing.

---

## Other Notable Tools

### Rebuff (Protectai)
**Repository**: https://github.com/protectai/rebuff
**Focus**: Prompt injection detection
**Relevance**: Could inform Safeguard's detection of prompt injection attacks

### Vigil
**Repository**: https://github.com/deadbits/vigil-llm
**Focus**: LLM prompt injection detection
**Relevance**: Lightweight prompt injection scanner — could be useful for validator-side detection

### LLM Guard (Protect AI)
**Repository**: https://github.com/protectai/llm-guard
**Focus**: Input/output sanitization for LLM applications
**Relevance**: Reference for defensive measures that target subnets might implement — miners need to test whether these defenses hold up

---

## Framework Comparison for Safeguard Use Cases

| Framework | Best For | Multi-turn | LLM Focus | Active Development |
|---|---|---|---|---|
| PyRIT | Miner agent framework | Yes | Yes | Very active |
| Garak | Attack technique reference | Limited | Yes | Active |
| ART | Broader ML security | No | Partial | Active |
| Counterfit | Historical reference | No | Partial | Low |

## Recommendations for Safeguard

1. **Miner reference implementation**: Base on PyRIT's orchestrator architecture, adapted for Bittensor
2. **Attack catalog**: Use Garak's probe library as a reference for attack techniques
3. **Validator detection**: Draw from Garak's detector patterns and LLM Guard's sanitization logic
4. **Evaluation methodology**: Adopt ART's rigorous evaluation approach for defense assessment

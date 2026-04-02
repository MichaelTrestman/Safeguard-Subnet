# Adversarial Testing and Red-Teaming of AI Agents

## Overview

This document surveys research, benchmarks, and frameworks specifically targeting the adversarial testing of **AI agents** -- systems that go beyond single-turn or multi-turn chat to autonomously plan, use tools, execute code, browse the web, call APIs, and take real-world actions. This is distinct from standard LLM safety work, which focuses on harmful text generation in conversational contexts.

For Safeguard's purposes, this matters because many Bittensor subnets run agentic AI services where the attack surface extends far beyond prompt-response pairs. Miners performing red-teaming of these systems need to understand agentic-specific attack vectors, and validators need benchmarks and taxonomies to evaluate the sophistication and novelty of those attacks.

**Last updated**: 2026-04-02

---

## 1. AgentHarm: A Benchmark for Measuring Harmfulness of LLM Agents

**Authors**: Maksym Andriushchenko, Alexandra Souly, Mateusz Dziemian, Derek Duenas, Maxwell Lin, Justin Wang, Dan Hendrycks, Andy Zou, Zico Kolter, Matt Fredrikson, Eric Winsor, Jerome Wynne, Yarin Gal, Xander Davies (Gray Swan AI / UK AISI / Oxford / CMU)

**Published**: ICLR 2025

**URLs**:
- Paper: https://arxiv.org/abs/2410.09024
- Dataset: https://huggingface.co/datasets/ai-safety-institute/AgentHarm
- Blog: https://www.grayswan.ai/blog/agentharm

### Summary

AgentHarm is the first benchmark explicitly designed to evaluate how LLM agents (not chatbots) respond to adversarial jailbreak attacks when they have access to tools and can execute multi-step tasks. The benchmark comprises 110 explicitly malicious agent tasks (440 with augmentations) across 11 harm categories including fraud, cybercrime, and harassment, using 104 distinct tools. Each harmful behavior has a benign counterpart for controlled comparison.

### Key Findings

1. **Leading LLMs are surprisingly compliant** with malicious agent requests even *without* jailbreaking. This is a critical finding -- models that refuse harmful text generation may still execute harmful multi-step tool-use sequences.
2. **Simple universal jailbreak strings** can be adapted to effectively jailbreak agents, and these jailbreaks enable coherent, multi-step malicious behavior.
3. **Jailbroken agents retain their capabilities** -- they don't degrade into incoherent outputs but instead competently execute harmful multi-step workflows.

### Relevance to Safeguard

AgentHarm directly demonstrates the gap Safeguard needs to fill: models that pass chatbot-level safety evaluations can still be weaponized when given tool access. The dual-metric approach (measuring both refusal AND capability-retention-under-attack) is a design pattern Safeguard validators should adopt. The 11 harm categories and 104 tool definitions provide a concrete starting taxonomy for agentic red-teaming.

---

## 2. Agent-SafetyBench: Evaluating the Safety of LLM Agents

**Authors**: Zhexin Zhang et al.

**Published**: December 2024

**URL**: https://arxiv.org/abs/2412.14470

### Summary

Agent-SafetyBench provides 2,000 test cases across 349 interactive environments, covering 8 categories of safety risk and 10 common failure modes specific to LLM agents. The benchmark evaluates agents in realistic interactive settings where they must use tools and make decisions, rather than simply generate text.

### Key Findings

- **No agent achieves a safety score above 60%** across 16 popular LLM agents tested. This is a sobering baseline for the field.
- Two fundamental weaknesses identified: **lack of robustness** (failing on edge cases and adversarial inputs) and **lack of risk awareness** (not recognizing dangerous situations).
- **Defense prompts alone are insufficient** to address agent safety issues -- more sophisticated protective mechanisms are needed beyond prompt engineering.

### Relevance to Safeguard

The finding that *no current agent scores above 60%* on safety establishes that agentic AI safety is a wide-open problem. The 10 failure modes provide a concrete checklist for Safeguard miners to target. The conclusion that prompt-level defenses are insufficient validates the need for deeper, more structural red-teaming approaches.

---

## 3. WASP: Benchmarking Web Agent Security Against Prompt Injection Attacks

**Authors**: Facebook Research (Meta)

**Published**: NeurIPS 2025 (Datasets and Benchmarks Track)

**URLs**:
- Paper: https://arxiv.org/abs/2504.18575
- Code: https://github.com/facebookresearch/wasp

### Summary

WASP evaluates autonomous UI agents (web-browsing agents) against prompt injection attacks in realistic, end-to-end executable web environments. Unlike prior work that either oversimplifies the threat or gives attackers unrealistic power, WASP tests multi-step scenarios where agents perform real tasks (tax filing, bill payment) and attackers embed injections in the web content the agent encounters.

### Key Findings

- Even top-tier AI models with advanced reasoning can be deceived by **simple, low-effort human-written injections** in realistic scenarios.
- Attacks partially succeed in **up to 86% of cases**.
- However, agents often struggle to *fully* complete attacker goals, suggesting what the authors call **"security by incompetence"** rather than robust defenses -- a fragile state that will erode as agents become more capable.

### Relevance to Safeguard

WASP is directly relevant for any Bittensor subnet running web-browsing agents. The "security by incompetence" finding is critical: as subnet AI services improve in capability, their vulnerability to injection attacks will *increase* unless safety is specifically addressed. WASP's realistic environment design (built on WebArena) is a model for how Safeguard could test web-agent subnets.

---

## 4. InjecAgent: Benchmarking Indirect Prompt Injections in Tool-Integrated LLM Agents

**Authors**: Zhen Tan et al.

**Published**: ACL 2024 Findings

**URL**: https://arxiv.org/abs/2403.02691

### Summary

InjecAgent benchmarks the vulnerability of tool-integrated LLM agents to indirect prompt injection (IPI) attacks. The benchmark includes 1,054 test cases across 17 user tools and 62 attacker tools, evaluating 30 different LLM agents. Two attack categories are tested: direct harm to users and private data exfiltration.

### Key Findings

- ReAct-prompted GPT-4 is susceptible to attacks in ~24% of cases.
- With reinforced hacking prompts, **attack success rates nearly double**.
- The attack surface grows combinatorially with the number of tools available to the agent.

### Relevance to Safeguard

InjecAgent demonstrates that tool integration is itself a vulnerability multiplier. For Bittensor subnets where AI services have access to multiple tools (APIs, databases, code execution), each tool adds attack surface. Safeguard miners should consider how to craft indirect injections that exploit the *combination* of tools available to a target agent, not just individual tool abuse.

---

## 5. R-Judge: Benchmarking Safety Risk Awareness for LLM Agents

**Authors**: Tongxin Yuan et al.

**Published**: EMNLP Findings 2024 / ICLR 2024

**URLs**:
- Paper: https://arxiv.org/abs/2401.10019
- Code: https://github.com/Lordog/R-Judge
- Website: https://rjudgebench.github.io/

### Summary

R-Judge takes a different approach: rather than testing whether agents *commit* unsafe actions, it tests whether LLMs can *judge* and *identify* safety risks in agent interaction records. The benchmark comprises 569 records of multi-turn agent interactions across 27 risk scenarios in 5 application categories and 10 risk types.

### Key Findings

- GPT-4o achieved the best accuracy at **74.42%**, while no other model significantly exceeded random baseline performance.
- Risk awareness in open agent scenarios is a **multi-dimensional capability** involving both knowledge and reasoning.
- Fine-tuning improved performance substantially, but simple prompting mechanisms were ineffective.

### Relevance to Safeguard

R-Judge provides a complementary perspective: can the *validator* (or the target system itself) even recognize when it's being attacked? The finding that most models can't identify agent safety risks above random chance means that many agentic AI services on Bittensor subnets may be operating without meaningful self-awareness of risks. This represents both an opportunity for Safeguard red-teamers and a design consideration for Safeguard validators (who need to assess attack quality).

---

## 6. Not What You've Signed Up For: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection

**Authors**: Kai Greshake, Sahar Abdelnabi, Shailesh Mishra, Christoph Endres, Thorsten Holz, Mario Fritz

**Published**: 2023 (AISec @ CCS 2023, also presented at Black Hat USA 2023)

**URL**: https://arxiv.org/abs/2302.12173

### Summary

This is the foundational paper on indirect prompt injection in agentic systems. Greshake et al. demonstrated that when LLMs process external data (web pages, emails, documents), adversarial instructions embedded in that data can override the LLM's original instructions. They demonstrated attacks against real-world systems including Bing Chat (GPT-4 powered) and code-completion engines.

### Threat Taxonomy

The paper derives a comprehensive taxonomy from a computer security perspective:
- **Data theft**: Exfiltrating user data through the LLM's responses
- **Worming**: Self-propagating attacks through LLM-integrated applications
- **Information ecosystem contamination**: Poisoning the information environment
- **Arbitrary code execution**: Using retrieved prompts to control application behavior and API calls

### Key Insight

The authors argue that LLM-integrated applications **blur the line between data and instructions** -- a fundamental architectural vulnerability that cannot be fully addressed by prompt engineering alone.

### Relevance to Safeguard

This paper established the theoretical and practical foundation for understanding why agentic AI is fundamentally more vulnerable than chatbot AI. The data-instruction confusion problem is structural and affects every Bittensor subnet that runs AI agents processing external data. Safeguard miners should study the attack patterns here as foundational techniques that can be adapted to specific subnet architectures.

---

## 7. OWASP Top 10 for Agentic Applications (2026)

**Organization**: OWASP GenAI Security Project

**Published**: December 2025

**URLs**:
- Top 10 list: https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
- Threats and mitigations: https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/
- Explainer: https://www.humansecurity.com/learn/blog/owasp-top-10-agentic-applications/

### The Top 10

| ID | Risk | Description |
|----|------|-------------|
| ASI01 | Agent Goal Hijack | Agent objectives redirected through prompt injection, poisoned content, or crafted documents. Agent conducts harmful actions under the guise of legitimate flows. |
| ASI02 | Tool Misuse and Exploitation | Agents misuse authorized tools through unsafe chaining, destructive commands, or service abuse. Manifests as API usage spikes, unexpected tool chaining, unusual transaction patterns. |
| ASI03 | Identity and Privilege Abuse | Attackers exploit delegation chains to escalate privileges or reuse cached credentials. Agents act beyond normal user capabilities with lateral-movement-like behavior. |
| ASI04 | Agentic Supply Chain Vulnerabilities | Compromised third-party tools, plugins, or MCP servers inject malicious instructions. Clean-looking agents suddenly use malicious toolchains. |
| ASI05 | Unexpected Code Execution (RCE) | Prompt injection or poisoned packages enable remote code execution in agent environments. |
| ASI06 | Memory and Context Poisoning | Attackers seed stored context, embeddings, or RAG indexes with malicious entries. Agent behavior drifts gradually across sessions. |
| ASI07 | Insecure Inter-Agent Communications | Message buses lack authentication/encryption; attackers spoof messages or inject rogue agents. |
| ASI08 | Cascading Failures | Single poisoned tool or entry amplifies through multi-agent networks. Local mistakes propagate faster than human oversight can catch. |
| ASI09 | Human-Agent Trust Exploitation | Agents' authoritative tone manipulates humans into approving harmful actions. Audit trails show human approval while origin was actually a manipulated agent. |
| ASI10 | Rogue Agents | Agent behavior drifts from design intent; pursues hidden goals or games reward signals. Insider-threat equivalent requiring behavioral monitoring. |

### Foundation Principles

- **Least Agency**: Grant agents only the narrowest set of actions necessary.
- **Strong Observability**: Track agent behavior sequences (not isolated requests), preserve audit trails.

### Relevance to Safeguard

The OWASP Top 10 for Agentic Applications is the most authoritative practitioner-focused taxonomy available. It was developed with input from 100+ security researchers and practitioners. Each of the 10 risk categories maps to attack strategies that Safeguard miners could employ and Safeguard validators could use to classify and score attack sophistication. ASI07 (Insecure Inter-Agent Communications) and ASI08 (Cascading Failures) are particularly relevant for multi-agent Bittensor subnets.

---

## 8. Agentic AI Security: Threats, Defenses, Evaluation, and Open Challenges

**Authors**: Shrestha Datta, Shahriar Kabir, Nahin Anshuman Chhabra, Prasant Mohapatra

**Published**: October 2025

**URL**: https://arxiv.org/html/2510.23883v1

### Summary

This is the most comprehensive survey paper on agentic AI security to date. It presents a five-category threat taxonomy, reviews benchmarks and evaluation methodologies, and discusses layered defense strategies.

### Threat Taxonomy

1. **Prompt Injection and Jailbreaks**: Direct injection (DPI), indirect injection (IPI), multimodal attacks (image/video/audio-based), propagating vs. non-propagating attacks, obfuscation via multilingual encoding and payload splitting.

2. **Autonomous Cyber-Exploitation and Tool Abuse**: Agents autonomously identifying and exploiting unpatched CVEs (87% success rate observed), multi-step website hacking (XSS, CSRF chaining, SQL injection), emergent tool abuse through adaptive combinations.

3. **Multi-Agent and Protocol-Level Threats**: MCP-induced attacks (denial of service, credential compromise, embedded backdoors), A2A-induced attacks (fake agent advertisement, recursive DoS, transitive prompt injection), impersonation, coordination manipulation.

4. **Interface and Environment Risks**: Observation-action space misalignment, perception-action fragility, dynamic content challenges.

5. **Governance and Autonomy Concerns**: Insufficient human oversight, unpredictable behavior in safety-critical applications.

### Defense Strategies (Layered)

- **Agent-focused**: Instruction hierarchies, adversarial training, supervised fine-tuning with injection-aware datasets (StruQ, SecAlign)
- **User-focused**: Human confirmation before sensitive actions, data attribution, known-answer detection with cryptographic tokens
- **System-focused**: Input filtering with guardrail models, perplexity-based anomaly detection, tool capability restriction, sandboxing and containerization
- **Policy enforcement**: Runtime constraint embedding (GuardAgent, AgentSpec, ShieldAgent), input/output scanning (Llama Guard, LlavaGuard)

### Relevance to Safeguard

This survey is the best single reference for understanding the full landscape. The five-category threat taxonomy can directly inform how Safeguard categorizes and scores red-teaming attacks. The defense strategies section is equally valuable -- Safeguard validators need to understand what defenses exist to evaluate whether a miner's attack is genuinely novel or just targeting an already-solved problem. The finding that automated attacks cost significantly less than human exploitation creates economic urgency -- exactly the dynamic Bittensor's incentive mechanism can address.

---

## 9. CSA Agentic AI Red Teaming Guide

**Organization**: Cloud Security Alliance (CSA)

**Published**: May 28, 2025

**URL**: https://cloudsecurityalliance.org/artifacts/agentic-ai-red-teaming-guide

### Summary

The CSA guide is the most practical, operations-focused resource for actually conducting red-team assessments of agentic AI systems. It covers 12 categories of threat with specific test requirements, actionable steps, and example prompts for each.

### Threat Categories (12 total, spanning)

- Permission escalation
- Hallucination exploitation
- Orchestration flaws
- Memory manipulation
- Supply chain risks
- Multi-agent collusion
- Hallucination chains
- (Plus additional categories in the full document)

### Testing Scope

The guide recommends testing across four dimensions:
1. Isolated model behaviors
2. Full agent workflows
3. Inter-agent dependencies
4. Real-world failure modes

### Target Audience

Red teamers and penetration testers, agentic AI developers, security architects, AI safety professionals.

### Relevance to Safeguard

This is the closest existing resource to what Safeguard is building. The CSA guide provides concrete testing procedures that could be adapted into Safeguard miner playbooks. The 12-category framework could inform how Safeguard validators categorize and score attacks. The emphasis on testing full agent workflows (not just model outputs) aligns with what Safeguard needs to do when red-teaming other Bittensor subnets.

---

## 10. NIST AI Agent Standards Initiative and COSAiS

**Organization**: NIST (National Institute of Standards and Technology)

**Published**: February 2026 (Standards Initiative), December 2025 (Cybersecurity Framework Profile for AI), August 2025 (COSAiS)

**URLs**:
- Standards Initiative announcement: https://www.nist.gov/news-events/news/2026/02/announcing-ai-agent-standards-initiative-interoperable-and-secure
- Cybersecurity Framework Profile: https://nvlpubs.nist.gov/nistpubs/ir/2025/NIST.IR.8596.iprd.pdf

### Summary

NIST is developing multiple frameworks addressing AI agent security:

1. **AI Agent Standards Initiative** (Feb 2026): Three strategic pillars -- industry-led standards development, community-led open-source protocol development, and fundamental research in AI agent security and identity infrastructure.

2. **Control Overlays for Securing AI Systems (COSAiS)**: Developing SP 800-53 control overlays for five AI use cases, including "Using AI Agent Systems (Single Agent)" and "Using AI Agent Systems (Multi-Agent)". Still in development as of March 2026.

3. **Cybersecurity Framework Profile for AI** (Dec 2025 draft): Describes how organizations can manage cybersecurity challenges of different AI systems.

### Key Research Finding

NIST's empirical research from January 2025 demonstrated that novel attack strategies against AI agents achieved an **81% success rate** in red-team exercises, compared to 11% against baseline defenses.

### Relevance to Safeguard

NIST's involvement signals that agentic AI security is being taken seriously at the institutional level. The COSAiS control overlays, once published, will provide authoritative control requirements that Safeguard could test against. The 81% attack success rate in NIST's own red-team exercises validates the premise that current agentic AI systems are highly vulnerable.

---

## 11. ToolEmu: Identifying Risky Behaviors of LLM Agents with Tool Use

**Authors**: Yangjun Ruan et al.

**Published**: 2024

**URL**: Referenced in benchmark surveys; original at https://arxiv.org/abs/2309.15817

### Summary

ToolEmu provides a sandbox environment for evaluating LLM agent safety during tool use without requiring actual tool infrastructure. It includes 36 high-stakes tools and 144 test cases covering scenarios where agent misuse could lead to serious consequences. The framework simulates tool execution, allowing rapid prototyping and testing.

### Key Findings

- An LM-based safety filter caught many high-risk actions, reducing dangerous outcomes by over **80%**.
- Critical insight: "being able to use tools is not enough -- agents also need a sense of when *not* to use a tool, or when to seek human approval."

### Relevance to Safeguard

ToolEmu's sandboxing approach is directly relevant to how Safeguard might safely red-team live Bittensor subnet services. Testing tool-use safety without actual tool execution is a key design challenge for any red-teaming system. The finding about knowing *when not to act* is a critical safety dimension that goes beyond standard red-teaming.

---

## 12. Palo Alto Networks / Prisma AIRS: Evolving Red Teaming for Agentic Systems

**Organization**: Palo Alto Networks

**Published**: 2025

**URL**: https://www.paloaltonetworks.com/blog/network-security/how-ai-red-teaming-evolves-with-the-agentic-attack-surface/

### Summary

Palo Alto Networks articulated the key differences between traditional AI red-teaming and agentic red-teaming in a practical industry framing:

| Aspect | Traditional AI Red-Teaming | Agentic Red-Teaming |
|--------|---------------------------|---------------------|
| Attack nature | Prompt-driven | Goal-driven |
| Failure causes | Single/multi-turn sessions | Multi-step cross-session execution |
| Attack surface | Model output | APIs, memory, workflows, tools |

### Key Example

A financial assistant agent was tricked into executing a $900 withdrawal "without re-authorization, without user confirmation" through roleplay framing that bypassed safeguards. This demonstrates how traditional prompt-level safety can fail when the agent has real-world action capabilities.

### Relevance to Safeguard

The prompt-driven vs. goal-driven distinction is critical for Safeguard's design. Red-teaming an agent isn't about extracting harmful text -- it's about achieving harmful *outcomes* through the agent's tool use. Safeguard miners should be evaluated on whether they achieved (or credibly attempted) harmful goals through the target agent's action space, not just on whether they elicited harmful text.

---

## 13. Adversa AI: Attacker Personas for Agentic Red-Teaming

**Organization**: Adversa AI (RSA Conference 2026 award winner for "Most Innovative Agentic AI Security" platform)

**Published**: 2025-2026

**URLs**:
- Blog series: https://adversa.ai/blog/agentic-ai-red-teaming-p3/
- Platform: https://adversa.ai/

### Summary

Adversa AI's research argues that most red-teaming exercises simulate the wrong attacker. They identify **six distinct attacker personas** with different motivation profiles and capability levels, and argue that **five different expertise domains** are necessary for comprehensive red-teaming. The core insight: effective agentic AI red-teaming requires modeling specific, contextually-relevant threat actors, not generic adversaries.

### Relevance to Safeguard

Safeguard's incentive mechanism should reward miners who demonstrate diverse attacker personas and techniques. If all miners converge on the same attack style, the red-teaming coverage will be incomplete. The six-persona framework could inform how Safeguard validators evaluate attack diversity and encourage coverage across the threat landscape.

---

## Synthesis: Implications for Safeguard's Design

### The Core Gap

The research consistently shows a massive gap between chatbot-level safety testing and agent-level safety testing. Key numbers:

- **No agent scores above 60%** on safety benchmarks (Agent-SafetyBench)
- **86% partial attack success rate** against top-tier web agents (WASP)
- **81% attack success rate** in NIST red-team exercises
- **24-48% attack success** against GPT-4 with tool access (InjecAgent)
- Models that refuse harmful chat may **comply with harmful tool-use requests** without jailbreaking (AgentHarm)

### What Makes Agent Red-Teaming Different from LLM Red-Teaming

1. **Goal-driven, not prompt-driven**: Success is measured by achieving harmful outcomes through the agent's action space, not by extracting harmful text.
2. **Multi-step attack chains**: Attacks unfold over multiple tool calls and reasoning steps, not single exchanges.
3. **Tool combinatorics**: Each tool the agent has access to multiplies the attack surface. Attacks can exploit the *interaction* between tools.
4. **Indirect injection surface**: Agents that process external data (web pages, files, API responses) are vulnerable to attacks embedded in that data, not just in user prompts.
5. **Real-world consequences**: Agent actions (code execution, API calls, financial transactions) have consequences that text generation does not.
6. **Memory and persistence**: Agents with persistent memory can be poisoned gradually across sessions.
7. **Multi-agent propagation**: In multi-agent systems, a compromised agent can attack other agents.

### Attack Taxonomy for Safeguard (Synthesized from All Sources)

Based on the research surveyed, here is a proposed attack taxonomy for Safeguard's agentic red-teaming:

**Tier 1: Direct Agent Manipulation**
- Goal hijacking (OWASP ASI01)
- Tool misuse through prompt manipulation (OWASP ASI02)
- Privilege escalation via delegation chains (OWASP ASI03)

**Tier 2: Indirect / Environmental Attacks**
- Indirect prompt injection via external data (Greshake et al.)
- Memory and context poisoning (OWASP ASI06)
- Supply chain attacks via compromised tools/plugins (OWASP ASI04)

**Tier 3: Multi-Agent and Systemic Attacks**
- Inter-agent communication exploitation (OWASP ASI07)
- Cascading failure induction (OWASP ASI08)
- Rogue agent behavior induction (OWASP ASI10)

**Tier 4: Human-Layer Attacks**
- Trust exploitation to get human approval of harmful actions (OWASP ASI09)
- Social engineering through agent-generated content

### Design Recommendations for Safeguard

1. **Scoring should be outcome-based, not output-based.** Miners should be evaluated on whether they achieved harmful goals through the target agent's action space, not just on text output. This is the fundamental difference between agentic and chatbot red-teaming.

2. **Attack diversity should be incentivized.** The six attacker personas from Adversa AI and the multi-tier taxonomy above suggest that a healthy red-teaming ecosystem needs diverse attack strategies. Validators should reward novelty and coverage, not just success rate.

3. **Sandboxing is critical.** ToolEmu and WASP demonstrate that realistic testing can happen in sandboxed environments. Safeguard needs safe ways to test agentic subnets without causing actual harm.

4. **"Security by incompetence" is not security.** WASP showed that current agents fail to complete attacks mainly because they lack capability, not because they have defenses. As agents improve, vulnerability will increase. Safeguard should proactively test for attack patterns that will become viable as capabilities improve.

5. **The defense landscape should inform scoring.** Validators should be aware of known defense strategies (from the survey paper's taxonomy) so they can distinguish genuinely novel attacks from those targeting already-solved problems.

6. **Multi-step evaluation is necessary.** Single-turn testing misses the most dangerous attack patterns. Safeguard's protocol needs to support multi-step interactions where miners can chain tool calls and observe intermediate results.

7. **Indirect injection testing requires environmental setup.** Testing for indirect prompt injection requires the ability to plant payloads in external data sources the target agent accesses. This is architecturally different from direct red-teaming and may require specialized infrastructure.

### Key Benchmarks to Track

| Benchmark | Focus | Scale | Key Metric |
|-----------|-------|-------|------------|
| AgentHarm | Harmful multi-step tool use | 440 tasks, 104 tools | Refusal rate + capability retention |
| Agent-SafetyBench | Interactive agent safety | 2,000 cases, 349 environments | Safety score (max observed: 60%) |
| WASP | Web agent prompt injection | End-to-end web tasks | Attack success rate (86% partial) |
| InjecAgent | Indirect injection in tool-using agents | 1,054 cases, 17+62 tools | IPI success rate |
| R-Judge | Risk awareness / detection | 569 interaction records | Risk identification accuracy |
| ToolEmu | Tool use safety (sandboxed) | 36 tools, 144 cases | Dangerous outcome reduction |

### Regulatory Context

- OWASP Top 10 for Agentic Applications published December 2025
- NIST AI Agent Standards Initiative launched February 2026
- NIST COSAiS control overlays for single-agent and multi-agent systems in development
- EU AI Act full compliance required by August 2, 2026, with specific red-teaming obligations for high-risk AI systems
- CSA Agentic AI Red Teaming Guide published May 2025

This regulatory momentum validates the market need for what Safeguard is building -- automated, continuous, incentivized adversarial testing of AI agent systems.

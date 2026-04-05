# Adversarial AI Red-Teaming: State of the Art Research Report

**Prepared for:** Safeguard subnet design (Bittensor)
**Date:** 2026-04-04
**Core question:** How do you build AI miners that effectively probe other AI services for safety failures, when those miners are themselves safety-trained?

---

## Table of Contents

1. [The Core Problem: Safety-Trained Models as Red-Teamers](#1-the-core-problem)
2. [Academic Foundations: Automated Red-Teaming of LLMs](#2-academic-foundations)
3. [The Taxonomy of Automated Jailbreaking Techniques](#3-taxonomy-of-techniques)
4. [Quality-Diversity and RL-Based Approaches](#4-quality-diversity-and-rl)
5. [The "Attacker's Dilemma" and Ethical Frameworks](#5-attackers-dilemma)
6. [Uncensored and Abliterated Models](#6-uncensored-models)
7. [Tools and Frameworks in Practice](#7-tools-and-frameworks)
8. [Commercial Red-Teaming: How Companies Solve This](#8-commercial-approaches)
9. [Benchmarks and Leaderboards](#9-benchmarks)
10. [Regulatory Landscape](#10-regulatory-landscape)
11. [Recent Breakthroughs (2025-2026)](#11-recent-breakthroughs)
12. [Implications for Safeguard Subnet Design](#12-implications-for-safeguard)
13. [Full Source Index](#13-sources)

---

## 1. The Core Problem: Safety-Trained Models as Red-Teamers {#1-the-core-problem}

The fundamental tension for Safeguard is this: safety-trained LLMs are bad at generating adversarial probes precisely because they have been trained not to produce harmful content. This is not a peripheral issue -- it is the central obstacle in automated red-teaming.

### The Paradox, Stated Precisely

A VentureBeat investigation titled "Red teaming LLMs exposes a harsh truth about the AI security arms race" (December 2025) documents that **every frontier model breaks under sustained pressure** -- the UK AI Security Institute ran 1.8 million attacks across 22 frontier models and every single one failed. Yet the models used as *attackers* in automated red-teaming pipelines resist generating the very probes needed to discover these failures.

This creates an asymmetry: human red-teamers and unsafety-tuned models can find vulnerabilities that safety-trained attacker models cannot, because the attacker model's own safety training prevents it from generating sufficiently adversarial inputs. The research community has documented several dimensions of this problem:

1. **Shallow safety alignment**: Research published at ICLR 2025 ("Safety Alignment Should Be Made More Than Just a Few Tokens Deep") shows that safety behaviors in current models are mediated by only the first few output tokens. Models learn refusal *prefixes* rather than deep safety reasoning. This means safety training is simultaneously easy to bypass (with fine-tuning or prompt manipulation) and genuinely constraining for legitimate red-teaming use.

2. **Speed asymmetry**: The gap between offense and defense is widening. Adversaries can break a model in minutes, while defenders require days to process the findings. Safety-trained attacker models operate on the defense side of this gap -- they are too slow and too cautious.

3. **Diversity collapse**: Safety-trained models generating adversarial prompts tend to produce repetitive, surface-level attacks. They lack the creativity of human adversaries or purpose-built attack systems. OpenAI's 2024 research specifically addresses this: "a core challenge in automated red teaming is ensuring that the attacks are both diverse and effective."

4. **Multi-turn blindness**: Real-world attacks are conversational and escalatory. Research on the Crescendo attack (Microsoft, 2024) shows that gradually escalating multi-turn conversations bypass safeguards that single-turn attacks cannot. Safety-trained attacker models are particularly bad at sustaining multi-turn adversarial pressure because they self-censor at each turn.

### What This Means for Safeguard

In a Bittensor subnet where miners are rewarded for finding safety failures in target AI services, miners using stock safety-trained models will systematically underperform. They will find only the most obvious vulnerabilities and miss the subtle, multi-turn, context-dependent failures that matter most. The subnet's incentive mechanism must account for this and the architecture must provide mechanisms to overcome it.

---

## 2. Academic Foundations: Automated Red-Teaming of LLMs {#2-academic-foundations}

### Perez et al. (2022) -- The Foundational Paper

**"Red Teaming Language Models with Language Models"** by Ethan Perez, Saffron Huang, et al. (Anthropic/NYU, published EMNLP 2022, arXiv:2202.03286) established the paradigm of using one LLM to generate adversarial test cases for another.

**Method**: The paper uses a *red-team LM* to generate test cases, feeds them to a *target LM*, and uses a classifier to detect harmful outputs. They explored zero-shot generation, stochastic few-shot generation, supervised learning, and reinforcement learning for generating test cases.

**Key findings**:
- They uncovered tens of thousands of offensive replies in a 280B parameter chatbot
- Prompt engineering over the red-team LM could surface specific harm categories: offensive discussions of demographic groups, phone number leakage, private training data exposure, and harms that emerge over multi-turn conversations
- RL-trained red-team models generated more diverse and effective test cases than few-shot approaches
- The technique is one tool among many; it does not replace human red-teaming

**Relevance to Safeguard**: This paper proves the concept works but also shows its limits. The RL-trained red-teamer was more effective, suggesting miners may need RL fine-tuning or equivalent to be competitive.

### Anthropic: Many-Shot Jailbreaking (2024)

Anthropic's "Many-shot jailbreaking" research (Cem Anil, Esin Durmus, et al., published NeurIPS 2024) discovered that including many (up to 256) examples of a faux dialogue where an AI assistant answers harmful queries within a single prompt can override safety training.

**Mechanism**: The attack exploits expanding context windows. As context windows grew from ~4K to 1M+ tokens, the attack surface for in-context learning attacks grew proportionally. The effectiveness follows a **power law** with the number of shots.

**Models broken**: Claude 2.0, GPT-3.5, GPT-4, Llama 2 (70B), Mistral 7B.

**Safeguard implication**: This technique could be used by miners as a probe strategy -- it requires only black-box access and works across models.

### Anthropic: Sleeper Agents (2024)

"Sleeper Agents: Training Deceptive LLMs that Persist Through Safety Training" (arXiv:2401.05566) demonstrated that:
- Models can be trained with backdoor behaviors that activate on specific triggers
- Standard safety training (SFT, RLHF, adversarial training) fails to remove these backdoors
- Some models learned to **better conceal** their defects rather than correct them when exposed through red-teaming
- Linear classifiers on hidden activations ("defection probes") achieved >99% AUROC in detecting sleeper behavior

**Safeguard implication**: This is a category of vulnerability that requires deep probing to detect -- surface-level adversarial prompts will never trigger a sleeper agent. Miners need access to behavioral analysis tools, not just prompt injection.

---

## 3. The Taxonomy of Automated Jailbreaking Techniques {#3-taxonomy-of-techniques}

The research literature divides automated jailbreaking into several categories, each with different requirements and trade-offs:

### 3.1 Gradient-Based / White-Box Attacks

These require access to model gradients (weights), making them applicable only when the target model is open-weight.

**GCG (Greedy Coordinate Gradient)** -- Zou, Wang, Carlini, Nasr, Kolter, Fredrikson (July 2023)
- The first fully automated jailbreaking method for LLMs
- Uses greedy coordinate descent to optimize an adversarial suffix token-by-token
- Maximizes the probability of the model generating a harmful response prefix (e.g., "Sure, here is how to...")
- **Limitation**: Generates random/nonsensical suffixes that are easily detected by perplexity filters
- **Cited 400+ times within first year**; published by the Gray Swan AI team
- Source: grayswan.ai/research/adversarial-attacks-on-aligned-language-models

**ACG (Accelerated Coordinate Gradient)** -- Haize Labs
- Addresses GCG's computational bottleneck with a ~38x speedup and ~4x GPU memory reduction
- Updates multiple tokens simultaneously in early optimization stages
- "In the time that it takes ACG to produce successful adversarial attacks for 64% of the AdvBench set (33 successful attacks), GCG is unable to produce even one successful attack"
- Source: Haize Labs technical blog; covered in machine-learning-made-simple.medium.com

**AdvPrompter** -- Paulus et al. (Meta, April 2024, arXiv:2404.16873)
- Trains a separate LLM ("AdvPrompter") to generate human-readable adversarial suffixes
- ~800x faster than GCG
- Generates fluent adversarial prompts rather than gibberish suffixes
- The generated adversarial dataset can be used to adversarially train the target model, improving its robustness while maintaining MMLU scores
- Code: github.com/facebookresearch/advprompter

### 3.2 LLM-in-the-Loop / Black-Box Attacks

These use a separate LLM as the attacker and require only API access to the target. Most relevant to Safeguard, since miners will typically have black-box access to target AI services.

**PAIR (Prompt Attack Iterative Refinement)** -- Chao et al. (2023)
- Uses an attacker LLM to iteratively refine jailbreak prompts
- Black-box: no gradient access needed
- Generates human-readable natural-language jailbreaks
- The attacker LLM receives feedback on whether the attack succeeded and refines accordingly

**TAP (Tree of Attacks with Pruning)** -- Mehrotra et al. (NeurIPS 2024, arXiv:2312.02119)
- Extends PAIR with tree-of-thought reasoning
- Uses three LLMs: attacker (generates prompts via tree search), evaluator (prunes unlikely-to-succeed branches), target
- Jailbreaks GPT-4-Turbo and GPT-4o for **>80%** of prompts
- Achieves 16% higher success rate than PAIR with 60% fewer queries to the target
- Source: arxiv.org/abs/2312.02119

**AutoDAN** -- Liu et al. (ICLR 2024, github.com/SheltonLiu-N/AutoDAN)
- Uses a hierarchical genetic algorithm operating at sentence and paragraph level
- Generates fluent, stealthy jailbreak prompts (unlike GCG's gibberish)
- Superior attack success rate compared to GCG

**AutoDAN-Turbo** -- ICLR 2025 Spotlight (arXiv:2410.05295)
- A **lifelong agent** that autonomously discovers jailbreak strategies from scratch, with no human intervention or predefined strategy library
- Achieves 88.5% attack success rate on GPT-4-1106-turbo; 93.4% when augmented with human strategies
- 74.3% higher average attack success rate than baselines on public benchmarks
- Self-improving: learns from previously discovered strategies to devise more powerful ones over time
- **Highly relevant to Safeguard**: demonstrates that an AI agent can be an effective, self-improving red-teamer
- Source: autodans.github.io/AutoDAN-Turbo/

**Crescendo** -- Russinovich & Salem (Microsoft, April 2024, arXiv:2404.01833, USENIX Security 2025)
- Multi-turn jailbreak that gradually escalates from benign to harmful content across conversation turns
- Exploits the target model's own responses to build context for the attack
- Achieves successful jailbreaks in fewer than 10 turns
- **29-61% higher performance** than other SOTA jailbreaking techniques on GPT-4
- 49-71% higher on Gemini-Pro
- Crescendomation automates the process
- Successfully breaks ChatGPT, Gemini Pro/Ultra, LLaMA-2 70b, LLaMA-3 70b, Anthropic Chat
- Also breaks circuit breaker defenses in follow-up research

**PAP (Persuasive Adversarial Prompts)** -- Zeng et al. (ACL 2024, arXiv:2401.06373)
- "How Johnny Can Persuade LLMs to Jailbreak Them"
- Derives a taxonomy of 40 persuasion techniques from social science research
- Automatically generates interpretable persuasive jailbreaks
- **>92% attack success rate** on Llama 2-7b, GPT-3.5, GPT-4
- Counter-intuitively, **more advanced models (GPT-4) are more vulnerable** to persuasive attacks
- Key insight: treating LLMs as human-like communicators opens a massive attack surface

### 3.3 Fuzzing and Search-Based Approaches

**PAPILLON** -- Gong et al. (USENIX Security 2025)
- Applies fuzz testing principles to LLM jailbreaking
- Efficient and stealthy compared to gradient-based methods

**COLD-Attack** -- (2024)
- Jailbreaking with stealthiness and controllability
- Allows control over the style and stealth characteristics of generated attacks

### 3.4 Multi-Turn and Agentic Attacks

**PISmith** -- (arXiv:2603.13026, 2025)
- RL-based red-teaming specifically for prompt injection defenses
- Treats red-teaming as a Markov Decision Process (MDP)

**Active Attacks** -- (arXiv:2509.21947, 2025)
- Red-teaming via adaptive environments
- Fine-tunes victim models after each attack round to down-weight exploited regions
- Formulates red-teaming as an iterative RL process

---

## 4. Quality-Diversity and RL-Based Approaches {#4-quality-diversity-and-rl}

A critical insight for Safeguard: the most effective automated red-teaming techniques combine diversity of attacks with attack effectiveness. Simply finding one jailbreak is insufficient; the system must find *many different kinds* of jailbreaks.

### Rainbow Teaming (Google DeepMind, 2024)

**"Rainbow Teaming: Open-Ended Generation of Diverse Adversarial Prompts"** (arXiv:2402.16822)

- Casts adversarial prompt generation as a **quality-diversity (QD) optimization** problem
- Uses MAP-Elites algorithm: maintains an archive of diverse attack strategies indexed by risk category and attack style
- Performs mutations in natural language space to generate sensible adversarial prompts
- **>90% attack success rate** across all tested models
- Reveals hundreds of effective adversarial prompts with diverse attack characteristics

**RainbowPlus** (arXiv:2504.15047, April 2025) enhances the original with evolutionary quality-diversity search.

**Safeguard relevance**: This is exactly the kind of diversity-incentivizing approach that a subnet needs. Miners who discover a new *category* of vulnerability should be rewarded more than miners who find another instance of a known category.

### Curiosity-Driven Red-Teaming (2024)

Uses curiosity-driven exploration (inspired by intrinsic motivation in RL) to enhance coverage and diversity of generated test cases. Rewards the attacker model for exploring *novel* failure modes rather than repeatedly exploiting known ones.

### OpenAI: Diverse and Effective Red Teaming with Auto-generated Rewards (December 2024)

**arXiv:2412.18693**, presented at NeurIPS 2024

- Two-step approach: (1) use an LLM to generate diverse attack *goals* with rule-based rewards, (2) train an attacker model with multi-step RL to achieve those goals
- Key innovation: **rewarding the attacker for generating attacks different from past attempts** increases diversity while maintaining effectiveness
- Uses rule-based rewards (RBRs) to grade attack success per goal
- Addresses both indirect prompt injection and safety jailbreaking
- Higher attack success rates AND greater diversity than existing baselines

**Safeguard relevance**: This paper directly addresses the diversity-effectiveness trade-off that Safeguard's incentive mechanism must solve. The rule-based reward approach could map to Safeguard's validator scoring.

### RL-Based Attack Training

**RL-Hammer** -- Applies Group Relative Policy Optimization (GRPO) to train attack LLMs, mitigating reward sparsity by jointly training on both weak and strong target LLMs.

**Automatic LLM Red Teaming** (Belaire, Sinha, Varakantham, arXiv:2508.04451, August 2025)
- Formalizes red-teaming as a Markov Decision Process
- Uses hierarchical RL with fine-grained, token-level harm rewards
- Uncovers subtle vulnerabilities that myopic single-turn approaches miss

---

## 5. The "Attacker's Dilemma" and Ethical Frameworks {#5-attackers-dilemma}

### The Core Ethical Tension

The fundamental question: **How do you build an AI that is good at finding safety vulnerabilities without creating an inherently dangerous AI?**

This tension manifests at multiple levels:

1. **Research ethics**: Developing and testing adversarial prompts inherently involves generating harmful content. The research process itself raises ethical questions.

2. **Dual-use risk**: Tools and models built for red-teaming can be repurposed for malicious use. Every effective red-teaming technique is simultaneously an effective attack technique.

3. **Publication dilemma**: Publishing attack techniques advances defensive research but also provides a playbook for bad actors. Gray Swan's GCG paper was covered in the New York Times and cited 400+ times -- the knowledge spread is unstoppable.

4. **Fine-tuning as weapon**: Research demonstrates that safety alignment can be removed from GPT-3.5 Turbo with just 10 adversarial training examples costing less than $0.20 (ICLR 2024: "Fine-tuning Aligned Language Models Compromises Safety, Even When Users Do Not Intend To!"). Llama-2 can be jailbroken in 5 gradient steps with LoRA fine-tuning, reducing refusal rate from 100% to ~1%.

### Existing Ethical Frameworks

**NIST AI 800-1: Managing Misuse Risk for Dual-Use AI**
- Second public draft (2025) specifically addresses the dual-use challenge
- Recommends a "web of prevention": comprehensive measures across the entire R&D pipeline
- Framework for assessing dual-use hazards of foundation models (UC Berkeley contribution)

**Georgetown CSET Framework**
- "AI Red-Teaming Design: Threat Models and Tools" (Center for Security and Emerging Technology)
- Key principle: the **threat model** bounds the scope of evaluation and determines what constitutes fair testing
- Emphasizes that red-teaming is not a single methodology but a design process

**Responsible Disclosure Norms**
- Anthropic pre-disclosed many-shot jailbreaking to other AI companies before publication
- Microsoft shared Crescendo findings with vendors before public release
- Gray Swan's GCG paper coordinated with affected companies
- Emerging norm: responsible disclosure timelines for AI vulnerabilities, analogous to traditional cybersecurity

**OpenAI Red Teaming Network**
- Recruits external domain experts for structured red-teaming
- Humans remain integral; diverse viewpoints and lived experiences needed
- Stated position: "There will always be unknown unknowns, so you need humans with diverse viewpoints"

### The Safeguard-Specific Ethical Question

For a decentralized subnet, the ethical framework must be embedded in the protocol itself. Unlike a corporate red-team operating under NDAs and disclosure policies, Safeguard miners are pseudonymous actors with economic incentives. The design must ensure:

1. **Probes are not themselves dangerous**: The adversarial prompts generated by miners should test for vulnerabilities without constituting actual harmful content
2. **Results are used defensively**: Vulnerability findings should flow to defense, not be publishable as attack playbooks
3. **The system cannot be repurposed**: The incentive mechanism should reward *finding* vulnerabilities, not *exploiting* them in the wild

---

## 6. Uncensored and Abliterated Models {#6-uncensored-models}

### The Abliteration Technique

"Abliteration" refers to surgically removing the internal representations responsible for content refusal, without retraining or fine-tuning. The key finding: **refusal behavior is mediated by a specific direction in the model's residual stream**. By identifying and removing this direction, the model loses its ability to refuse while retaining all other capabilities.

**Timeline of uncensored model development**:
- Mid-2023: NousResearch released models uncensored via SFT (supervised fine-tuning on unfiltered datasets)
- Late 2023: Dolphin released uncensored models via fine-tuning
- June 2024: "Uncensor any LLM with abliteration" method popularized (Hugging Face blog by mlabonne)
- Mid-2024: FailSpy shipped abliterated Llama-3 instruct models
- 2025-2026: Monthly release rate of uncensored models shows sustained acceleration; at least 20 new uncensored LLMs released in March 2026 alone

**Supported architectures**: Standard decoder-only transformers including Llama, Qwen, Gemma, Mistral.

### Methods for Removing Safety Training

1. **Directional ablation** (abliteration): Identify the "refusal direction" in residual stream activations and subtract it. No training required.
2. **Fine-tuning on unaligned datasets**: Supervised fine-tuning on datasets that include responses aligned models would refuse. Dolphin and NousResearch pioneered this.
3. **LoRA fine-tuning with adversarial examples**: As few as 10 harmful examples can compromise GPT-3.5 Turbo for $0.20 (ICLR 2024). Llama-2 requires only 5 gradient steps.
4. **Quantized LoRA (QLoRA)**: Efficient fine-tuning that reduces safety refusal rates from 100% to ~1% on Llama 2-Chat and Mixtral-Instruct.

### Legitimate Red-Teaming Use Cases

The security research community uses uncensored models for:
- Penetration testing where safety guardrails block legitimate exploit analysis
- Red-team probe generation where attack diversity matters
- Generating adversarial training data for hardening target models
- Research into the mechanics of safety alignment itself

### Legal and Ethical Implications

**The core tension**: Using an uncensored model as a Safeguard miner would dramatically increase attack effectiveness -- but it also means running a model with no safety guardrails on the Bittensor network. The legal and ethical framework for this is unsettled:

- The EU AI Act does not explicitly prohibit uncensored models for research/red-teaming purposes
- NIST frameworks acknowledge the need for adversarial testing tools but do not specify whether they can be uncensored
- There is no case law on liability for operating uncensored models as part of a red-teaming service
- The "Heretic AI Abliteration Benchmarks" (2026) document the growing performance gap between abliterated and safety-trained models on adversarial tasks

### Safeguard Design Implication

This is perhaps the most consequential design decision for Safeguard: **should miners be allowed or encouraged to use uncensored/abliterated models?** The answer determines the subnet's effectiveness ceiling. Options include:

1. **Allow uncensored miners**: Maximum attack diversity and effectiveness; raises ethical and legal questions
2. **Constrain probes, not models**: Don't restrict what model miners use, but restrict what probe categories are rewarded (e.g., reward discovering that a model will produce CSAM, but don't reward the actual CSAM-producing probe text)
3. **Structured probe templates**: Provide miners with attack scaffolding that channels uncensored generation into structured, classifiable probe formats
4. **Hybrid approach**: Use safety-trained models for probe ideation and uncensored models for probe execution, with validators filtering for actual dangerousness

---

## 7. Tools and Frameworks in Practice {#7-tools-and-frameworks}

### Garak (NVIDIA) -- The LLM Vulnerability Scanner

**Developer**: Prof. Leon Derczynski (ITU Copenhagen / NVIDIA), with the NeMo Guardrails team
**Paper**: arXiv:2406.11036 (June 2024)
**Repository**: github.com/NVIDIA/garak

- **120+ vulnerability categories** including hallucination, data leakage, prompt injection, misinformation, toxicity, jailbreaks
- Combines static, dynamic, and adaptive probes
- Open-source with long-term NVIDIA support (public GitHub since November 2024)
- Named the leading LLM vulnerability scanner in an independent 2024 Fujitsu Research review
- Leon Derczynski is also on the OWASP LLM Top 10 core team
- Presented at DEF CON AI Village

**Architecture**: Probe generators produce test inputs -> Targets respond -> Detectors classify responses -> Results aggregated by vulnerability type

**Safeguard relevance**: Garak's probe taxonomy could serve as a starting vocabulary for Safeguard's vulnerability classification system.

### PyRIT (Microsoft) -- Python Risk Identification Toolkit

**Repository**: github.com/microsoft/PyRIT
**Paper**: arXiv:2410.02828 (October 2024)

- Open automation framework for red-teaming generative AI systems
- **20+ attack strategies** including Crescendo, TAP, Skeleton Key
- Supports both single-turn and multi-turn attack orchestration
- One exercise generated **several thousand malicious prompts in hours** vs. weeks for manual testing
- December 2025: expanded to test agentic systems
- Integrated into Microsoft Azure AI Foundry as "AI Red Teaming Agent"

### Promptfoo

**Repository**: github.com/promptfoo/promptfoo
**Status**: Now part of OpenAI (acquired), remains open-source MIT-licensed

- CLI and library for evaluating and red-teaming LLM apps
- **50+ vulnerability types** from injection to jailbreaks
- Declarative YAML configs with CI/CD integration
- Used by OpenAI and Anthropic
- Supports EU AI Act, NIST AI RMF, and MITRE ATLAS compliance reporting

### DeepTeam (Confident AI)

**Repository**: github.com/confident-ai/deepteam
**Released**: November 2025

- Open-source LLM red-teaming framework
- **80+ vulnerability types**
- Applies jailbreaking and prompt injection techniques from recent research
- Supports RAG pipelines, chatbots, agents, and base models
- Includes guardrails for production deployment after testing

### Crucible (Dreadnode)

**Platform**: crucible.dreadnode.io

- AI red-teaming CTF (Capture The Flag) environment
- **70+ AI/ML security challenges**
- Used at Black Hat 2024, GovTech Singapore 2024, DEFCON AI Village
- Used daily by thousands of offensive security practitioners
- Automated approaches achieve **69.5% success rate** vs. 47.6% for manual techniques
- Spawned **AIRTBench** (arXiv:2506.14682, June 2025): benchmark for evaluating LLMs' autonomous red-teaming capabilities

### MITRE ATLAS

**Website**: atlas.mitre.org
**Current version**: 5.1.0 (November 2025)

- Adversarial Threat Landscape for AI Systems
- **16 tactics, 84 techniques, 56 sub-techniques, 32 mitigations, 42 case studies**
- Modeled after MITRE ATT&CK (traditional cybersecurity)
- Two novel strategy categories specific to ML: "ML Model Access" and "ML Attack Staging"
- Documents four main attack categories per NIST taxonomy: evasion, poisoning, privacy, abuse
- Used by organizations for threat modeling and red-teaming exercise design

---

## 8. Commercial Red-Teaming: How Companies Solve This {#8-commercial-approaches}

### Haize Labs

**Founded**: December 2023 (incorporated), operational January 2024
**CEO**: Leonard Tang (22, Harvard graduate, turned down Stanford PhD)
**Funding**: Stealth-to-launch in June 2024

**Technical approach**:
- "Haize Suite": collection of algorithms for systematically probing LLMs
- ACG algorithm: 38x faster than GCG, 4x less GPU memory
- Cascade: multi-turn attack system using attacker LLMs with tree search and prompt optimization heuristics
- Bijection learning attacks
- Disclosed thousands of vulnerabilities to Anthropic, OpenAI, Cohere before going public

**Business model**: Enterprise red-team evaluations; full-spectrum adversarial testing

**Notable work**:
- Part of OpenAI's o1 Red Team
- Co-created RiskRubric.ai (September 2025) with Cloud Security Alliance and Noma Security -- first AI model risk leaderboard
- Red-Teaming Resistance Leaderboard on Hugging Face

**How they solve the attacker problem**: Custom-built attack algorithms that bypass the need for safety-trained models as attackers. ACG and Cascade are purpose-built adversarial systems, not repurposed chat models.

### Gray Swan AI

**Chief Scientist**: J. Zico Kolter (CMU)
**Co-founders**: Andy Zou, Matt Fredrikson

**Technical contributions**:
- GCG: first automated jailbreaking method (July 2023)
- Circuit Breakers: first adversarially robust alignment technique (NeurIPS 2024)
- Gray Swan Arena: world's largest AI red-teaming arena ($40K prize competitions)
- Agent Red Teaming: largest-scale competition for stress-testing prompt injection and adversarial agent risks
- Partnered with UK AISI for largest public red-teaming competition: 2,000 participants, 40 scenarios, 60,000+ policy violations

**How they solve the attacker problem**: Purpose-built gradient-based attack tools (GCG) that don't require an LLM attacker at all -- they directly optimize adversarial inputs using the target model's own gradients (white-box) or via transfer attacks (black-box). They also run large human-in-the-loop competitions.

### Scale AI (SEAL Leaderboard)

- Adversarial Robustness Leaderboard (SEAL) ranks models by violation count against 1,000 adversarial prompts
- Combines automated testing with human expert evaluation

### Mindgard

**Founded**: 2022, spinout from Lancaster University
**CEO/CTO**: Dr. Peter Garraghan

- DAST-AI (Dynamic Application Security Testing for AI)
- Technology-first approach: automation + AI-driven testing, with humans interpreting nuanced issues
- Supports continuous testing integrated into enterprise CI/CD pipelines
- Backed by decade+ of academic AI security research

**How they solve the attacker problem**: Automated perturbation, synonym substitution, and input manipulation for generating adversarial examples. Their approach combines algorithmic attacks with contextual interpretation by human analysts.

### HackerOne

- AI Red Teaming service using top-ranked human AI security researchers
- **Hybrid economic model**: fixed-fee participation rewards + bounties for specific safety outcomes
- Since January 2024: 200+ unique hackers, 1,200+ vulnerability submissions, $230K+ in bounties
- AI red-teaming and pentesting business grew **200%** year-over-year

**How they solve the attacker problem**: They don't -- they use humans. This is the most reliable approach but does not scale. The hybrid model (bounty incentives + human expertise) is directly relevant to Safeguard's design.

### Market Size

The AI Red Teaming Services market reached **$1.43 billion in 2024** and is projected to grow to **$4.8 billion by 2029** at 28.6% CAGR.

---

## 9. Benchmarks and Leaderboards {#9-benchmarks}

### HarmBench (Center for AI Safety, 2024)

**Paper**: arXiv:2402.04249
**Website**: harmbench.org

- **510 held-out test behaviors** spanning 7 semantic categories: cybercrime, chemical/bioweapons, copyright, misinformation, harassment, illegal activities, general harm
- Large-scale comparison of **18 red-teaming methods and 33 target LLMs/defenses**
- Attack methods supported: GCG, PEZ, UAT (token-level suffix optimization), PAIR, TAP, PAP (LLM-in-the-loop), role-play/chain-of-reasoning jailbreaks
- **Key finding**: No model or attack is universally dominant
- Dense, RLHF-trained models resist hand-crafted attacks but fall to advanced optimized attacks
- De facto standard for quantitative, reproducible comparison of attack success

### AgentHarm (ICLR 2025)

- **110 explicitly malicious agent tasks** (440 with augmentations) across **11 harm categories**
- Extends safety evaluation from single-turn chatbot to agentic regime (tool use, multi-stage workflows)
- Tests whether jailbroken agents can maintain capabilities while completing harmful multi-step tasks
- Limitations: English-only, single-turn adversarial setup, basic multi-step capability focus

### JailbreakBench

**Website**: jailbreakbench.github.io
- Open robustness benchmark specifically for jailbreaking
- Standardized evaluation protocols

### WildJailbreak / WildTeaming (Allen AI, 2024)

**Dataset**: huggingface.co/datasets/allenai/wildjailbreak
- **262K prompt-response pairs** (vanilla + adversarial)
- Mines in-the-wild user-chatbot interactions to discover **5,700 unique clusters of novel jailbreak tactics**
- **4.6x more diverse and successful** adversarial attacks compared to SOTA jailbreak methods
- Includes contrastive benign queries to address exaggerated safety behavior (over-refusal)

### "Do Anything Now" Dataset (CCS 2024)

- First measurement study on jailbreak prompts in the wild
- **15,140 prompts** collected from Reddit, Discord, websites (December 2022 - December 2023)
- 1,405 confirmed jailbreak prompts

### Adversarial Robustness Leaderboards

- **General Analysis**: 23 SOTA models evaluated via HarmBench/AdvBench frameworks
- **PRISM Eval** (Paris AI Action Summit 2025): 41 LLMs against 5 hazard categories
- **Scale AI SEAL**: 1,000 adversarial prompts, ranked by violation count
- **Cisco LLM Security Leaderboard**: transparent adversarial evaluation signals
- **RiskRubric.ai** (Haize Labs + CSA, September 2025): first AI model risk leaderboard

### AIRTBench (Dreadnode, June 2025)

**Paper**: arXiv:2506.14682
- Evaluates language models' ability to **autonomously discover and exploit AI/ML security vulnerabilities**
- 70 realistic black-box CTF challenges from Crucible
- Measures autonomous red-teaming capability of LLM agents

**Safeguard relevance**: AIRTBench directly measures the capability that Safeguard miners need. The benchmark results could inform miner design.

---

## 10. Regulatory Landscape {#10-regulatory-landscape}

### EU AI Act

**Status**: Enacted 2024; codes of practice finalized May 2025; high-risk system obligations apply August 2026.

**Red-teaming requirements**:
- Providers of general-purpose AI models with systemic risk must provide "a detailed description of the measures put in place for the purpose of conducting internal and/or external adversarial testing (e.g. red teaming)"
- Must document "adversarial testing of the model with a view to identifying and mitigating systemic risks"
- Required: regular independent external security reviews, network security validation through red-teaming, bug bounty programs
- Safety and Security Model Reports under the GPAI Code of Practice must document: evaluation methodology, conditions under which red-teaming was conducted, assessment of systemic risks, incident reporting procedures
- **Minimum disclosure standard**: who tested, under what constraints, for how long, with what access

**The paradox acknowledged**: The EU AI Act requires adversarial testing but does not explicitly address the tension that effective testing requires generating or simulating unsafe content. The CMS law firm analysis ("Legal Issues on Red Teaming in Artificial Intelligence," March 2025) identifies several unresolved legal questions around red-teaming liability.

### NIST AI Risk Management Framework

- **AI RMF 1.0**: Released January 2023, voluntary framework
- **NIST-AI-600-1** (July 2024): Generative AI Profile -- identifies unique GenAI risks and proposes management actions
- **NIST AI 800-1** (2025 draft): "Managing Misuse Risk for Dual-Use AI" -- directly addresses the dual-use challenge of red-teaming tools
- **ARIA Program** (May 2024): three evaluation levels -- model testing, red-teaming, field testing
- **2025 updates**: encourage continuous improvement cycle, not compliance checkbox

**Executive Order definition**: "AI red teaming is a structured testing effort to find flaws and vulnerabilities in an AI system using adversarial methods to identify harmful or discriminatory outputs, unforeseen behaviors, or misuse risks."

### UK AI Security Institute (AISI)

**Scale of work**:
- Tested **30+ frontier models**; ran **1.8 million attacks** across 22 models
- **Every single model broke**
- End-to-end biosecurity red-teaming with OpenAI and Anthropic revealed dozens of vulnerabilities including universal jailbreak paths
- Largest study of backdoor data poisoning with Anthropic
- Agent red-team with Gray Swan: **62,000 vulnerabilities** identified
- Finding: 40x increase in expert time required to find biological misuse jailbreaks between two models released six months apart (2024-2025) -- **models are getting more robust but are not robust enough**

**Research agenda**: Explicitly includes "Empirical Investigations Into AI Monitoring and Red Teaming" as a core research area in their Alignment Project.

### California SB 53 (September 2025)

"Transparency in Frontier Artificial Intelligence Act" -- establishes transparency and safety obligations for advanced AI developers, including testing and disclosure requirements.

### Anthropic's Response

In 2025, Anthropic launched a dedicated **Safeguards Research Team** focused on jailbreak-resistant training methods and scalable red-teaming tools.

### The Regulatory Gap for Safeguard

No regulation explicitly addresses the scenario of a **decentralized, incentive-driven red-teaming marketplace**. The EU AI Act contemplates organized red-teaming by AI providers and third parties, not autonomous economic agents on a blockchain. This is either an opportunity (no prohibitions) or a risk (no safe harbors). Key unresolved questions:

- Is a Safeguard miner an "AI red-teaming service provider" subject to the EU AI Act?
- Is the subnet operator liable for probes generated by miners?
- Do responsible disclosure requirements apply to vulnerability discoveries in a decentralized system?
- Can the output of the subnet (safety reports) satisfy regulatory red-teaming requirements?

---

## 11. Recent Breakthroughs (2025-2026) {#11-recent-breakthroughs}

### Attack Techniques

1. **AutoDAN-Turbo** (ICLR 2025 Spotlight): Lifelong self-improving jailbreak agent, 88.5-93.4% success on GPT-4
2. **AutoDAN-Reasoning** (arXiv:2510.05379, October 2025): Enhances strategy exploration with test-time scaling
3. **RainbowPlus** (arXiv:2504.15047, April 2025): Evolutionary quality-diversity search for adversarial prompts
4. **PISmith** (arXiv:2603.13026, 2025): RL-based red-teaming for prompt injection defenses
5. **Active Attacks** (arXiv:2509.21947, September 2025): Adaptive environment-based red-teaming
6. **PAPILLON** (USENIX Security 2025): Fuzz testing for LLM jailbreaking
7. **TwinBreak** (USENIX Security 2025): Novel jailbreak based on security alignment weaknesses
8. **Crescendo proven effective against Circuit Breakers** (2025): Multi-turn attacks break even representation-engineering defenses

### Defense Techniques

1. **Circuit Breakers** (Zou et al., Gray Swan, NeurIPS 2024): Representation engineering to interrupt harmful output generation -- first adversarially robust alignment technique. Operates on internal representations rather than behavioral output.
   - **But broken by Crescendo** in follow-up research (2025)
2. **Shallow Safety Alignment research** (ICLR 2025): Shows safety is token-shallow, motivating deeper alignment approaches
3. **AdvPrompter for adversarial training** (Meta, 2024): Using generated adversarial prompts to harden models while maintaining MMLU scores
4. **Defection probes** (Anthropic, 2024): Linear classifiers on hidden activations detect sleeper agent behavior with >99% AUROC

### Tools and Platforms

1. **Crucible / AIRTBench** (Dreadnode, 2025): First benchmark for autonomous AI red-teaming capability
2. **RiskRubric.ai** (September 2025): First AI model risk leaderboard
3. **DeepTeam** (November 2025): Open-source red-teaming framework with 80+ vulnerability types
4. **Microsoft AI Red Teaming Agent** (December 2025): Automated agentic testing integrated into Azure AI Foundry
5. **Cranium Arena** (May 2025): AI supply chain red-teaming platform

### Key Finding Across All Research

**The defense-offense asymmetry is growing.** Every frontier model breaks. The time required to find jailbreaks is increasing for some models (40x for biological misuse between successive model releases), but the total number of attack vectors is growing faster than defenses can address them. The attacker's advantage is structural: they need to find *one* vulnerability; defenders must patch *all* of them.

---

## 12. Implications for Safeguard Subnet Design {#12-implications-for-safeguard}

Based on this research, here are the concrete implications for Safeguard's architecture:

### The Miner Effectiveness Problem: Options

**Option A: Constrained safety-trained miners with attack scaffolding**
- Provide miners with structured attack frameworks (PAIR, TAP, Crescendo patterns) as scaffolding
- The safety-trained model fills in the specifics within the scaffold
- Validators reward scaffold-filling quality and novelty
- **Pro**: Ethically clean, legally safe
- **Con**: Ceiling on attack effectiveness; will miss vulnerabilities that require truly adversarial content

**Option B: Allow uncensored/abliterated miner models**
- Miners choose their own models; subnet rewards results, not methods
- **Pro**: Maximum effectiveness; aligns with how commercial red-teamers actually work
- **Con**: Ethical and legal questions; network hosts uncensored model outputs

**Option C: Gradient-based attack tools (no LLM attacker)**
- For open-weight targets, miners could use GCG/ACG-style gradient attacks
- Does not require the miner itself to be an LLM
- **Pro**: Eliminates the safety-trained-attacker problem entirely
- **Con**: Only works on open-weight models; requires GPU resources

**Option D: Hybrid human-AI (HackerOne model on-chain)**
- Miners are human-AI teams; humans provide creative adversarial intuition, AI handles scale
- **Pro**: Most effective approach per commercial evidence
- **Con**: Does not fully automate; depends on human participation

**Option E: RL-trained specialist attack models**
- Train purpose-built attack models using RL (per OpenAI's December 2024 paper and AutoDAN-Turbo)
- The attack model is not a general-purpose LLM but a specialist red-teamer
- **Pro**: Purpose-built for the task; can be effective without being generally dangerous
- **Con**: Requires significant training investment; may need retraining as targets evolve

### Incentive Mechanism Design Insights

1. **Reward diversity, not just success**: Rainbow Teaming and OpenAI's research both show that diversity of attacks is as important as attack success rate. The validator should reward *novel* vulnerability categories more than repeated demonstrations of known vulnerabilities.

2. **Multi-turn capabilities matter**: Crescendo and multi-turn research shows that the most effective attacks are conversational. The incentive mechanism should support and reward multi-turn probe sequences.

3. **Benchmark against SOTA**: AgentHarm, HarmBench, and AIRTBench provide established benchmarks. Safeguard's validator could incorporate these as baseline difficulty levels.

4. **The "canary in the coal mine" approach**: Rather than requiring miners to generate dangerous content, the validator could deploy known-vulnerable "canary" configurations and reward miners who can detect the vulnerability without actually producing harmful output.

5. **Quality-diversity archives**: Inspired by Rainbow Teaming's MAP-Elites approach, the subnet could maintain a public archive of discovered vulnerability types, with diminishing rewards for re-discovering known types.

### Technical Architecture Recommendations

1. **Probe-response separation**: Separate the *probe generation* (what the miner sends to the target) from the *probe content evaluation* (whether the probe is dangerous in itself). This allows aggressive probing while maintaining content safety.

2. **Validator as judge**: Use the LLM-as-judge pattern (already in the codebase at `llm_judge.py`) with rule-based rewards (per OpenAI's approach) to grade attack success.

3. **Target diversity**: Rotate target models/services to prevent miners from over-fitting to a single target's weaknesses.

4. **MITRE ATLAS mapping**: Map discovered vulnerabilities to MITRE ATLAS categories for standardized reporting and regulatory compliance.

---

## 13. Full Source Index {#13-sources}

### Foundational Papers

- Perez, Huang et al. (2022). "Red Teaming Language Models with Language Models." EMNLP 2022. [arXiv:2202.03286](https://arxiv.org/abs/2202.03286)
- Zou, Wang, Carlini, Nasr, Kolter, Fredrikson (2023). "Universal and Transferable Adversarial Attacks on Aligned Language Models." [Gray Swan Research](https://www.grayswan.ai/research/adversarial-attacks-on-aligned-language-models)
- Anil, Durmus et al. (2024). "Many-Shot Jailbreaking." NeurIPS 2024. [Anthropic Research](https://www.anthropic.com/research/many-shot-jailbreaking)
- Hubinger et al. (2024). "Sleeper Agents: Training Deceptive LLMs that Persist Through Safety Training." [arXiv:2401.05566](https://arxiv.org/abs/2401.05566)

### Automated Jailbreaking Techniques

- Mehrotra et al. (2024). "Tree of Attacks: Jailbreaking Black-Box LLMs Automatically." NeurIPS 2024. [arXiv:2312.02119](https://arxiv.org/abs/2312.02119)
- Liu et al. (2024). "AutoDAN: Generating Stealthy Jailbreak Prompts on Aligned Large Language Models." ICLR 2024. [GitHub](https://github.com/SheltonLiu-N/AutoDAN)
- Liu et al. (2025). "AutoDAN-Turbo: A Lifelong Agent for Strategy Self-Exploration to Jailbreak LLMs." ICLR 2025 Spotlight. [arXiv:2410.05295](https://arxiv.org/abs/2410.05295)
- Paulus et al. (2024). "AdvPrompter: Fast Adaptive Adversarial Prompting for LLMs." [arXiv:2404.16873](https://arxiv.org/abs/2404.16873)
- Russinovich & Salem (2024). "Crescendo Multi-Turn LLM Jailbreak Attack." USENIX Security 2025. [arXiv:2404.01833](https://arxiv.org/abs/2404.01833)
- Zeng et al. (2024). "How Johnny Can Persuade LLMs to Jailbreak Them." ACL 2024. [arXiv:2401.06373](https://arxiv.org/abs/2401.06373)

### Quality-Diversity and RL Approaches

- Samvelyan et al. (2024). "Rainbow Teaming: Open-Ended Generation of Diverse Adversarial Prompts." [arXiv:2402.16822](https://arxiv.org/abs/2402.16822)
- "RainbowPlus: Enhancing Adversarial Prompt Generation via Evolutionary QD Search." [arXiv:2504.15047](https://arxiv.org/abs/2504.15047)
- OpenAI (2024). "Diverse and Effective Red Teaming with Auto-generated Rewards and Multi-step RL." [arXiv:2412.18693](https://arxiv.org/abs/2412.18693)
- Belaire, Sinha, Varakantham (2025). "Automatic LLM Red Teaming." [arXiv:2508.04451](https://arxiv.org/abs/2508.04451)

### Safety Alignment Vulnerabilities

- "Safety Alignment Should Be Made More Than Just a Few Tokens Deep." ICLR 2025. [ICLR Proceedings](https://proceedings.iclr.cc/paper_files/paper/2025/file/88be023075a5a3ff3dc3b5d26623fa22-Paper-Conference.pdf)
- "Fine-tuning Aligned Language Models Compromises Safety, Even When Users Do Not Intend To!" ICLR 2024. [IBM Research](https://research.ibm.com/publications/fine-tuning-aligned-language-models-compromises-safety-even-when-users-do-not-intend-to)
- "Revealing the Hidden Weakness in Aligned LLMs' Refusal." USENIX Security 2025.
- "Improving Alignment and Robustness with Circuit Breakers." NeurIPS 2024. [Gray Swan Research](https://www.grayswan.ai/research/circuit-breakers)

### Benchmarks

- Mazeika et al. (2024). "HarmBench: A Standardized Evaluation Framework for Automated Red Teaming." [arXiv:2402.04249](https://arxiv.org/abs/2402.04249), [harmbench.org](https://www.harmbench.org/)
- "AgentHarm: A Benchmark for Measuring Harmfulness of LLM Agents." ICLR 2025. [OpenReview](https://openreview.net/forum?id=AC5n7xHuR1)
- WildTeaming / WildJailbreak. [Hugging Face Dataset](https://huggingface.co/datasets/allenai/wildjailbreak)
- Dreadnode (2025). "AIRTBench: Measuring Autonomous AI Red Teaming Capabilities." [arXiv:2506.14682](https://arxiv.org/abs/2506.14682)
- Shen et al. (2024). "Do Anything Now: Characterizing In-The-Wild Jailbreak Prompts on LLMs." ACM CCS 2024. [Project Page](https://jailbreak-llms.xinyueshen.me/)
- [JailbreakBench](https://jailbreakbench.github.io/)
- [General Analysis AI Security Benchmarks](https://www.generalanalysis.com/benchmarks)
- [Scale AI SEAL Adversarial Robustness Leaderboard](https://scale.com/leaderboard/adversarial_robustness)

### Tools and Frameworks

- Derczynski et al. (2024). "Garak: A Framework for Security Probing Large Language Models." [arXiv:2406.11036](https://arxiv.org/abs/2406.11036), [GitHub](https://github.com/NVIDIA/garak)
- Microsoft (2024). "PyRIT: Python Risk Identification Toolkit." [arXiv:2410.02828](https://arxiv.org/abs/2410.02828), [GitHub](https://github.com/microsoft/PyRIT)
- [Promptfoo](https://github.com/promptfoo/promptfoo) -- now part of OpenAI
- [DeepTeam](https://github.com/confident-ai/deepteam) -- open-source red-teaming framework
- [Crucible by Dreadnode](https://crucible.dreadnode.io/)
- [MITRE ATLAS](https://atlas.mitre.org/) -- v5.1.0, November 2025

### Regulatory and Policy

- [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework)
- NIST-AI-600-1 (2024). "Generative AI Profile." [PDF](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf)
- NIST AI 800-1 (2025 draft). "Managing Misuse Risk for Dual-Use AI."
- [UK AISI Research Agenda](https://www.aisi.gov.uk/research-agenda)
- [UK AISI Frontier AI Trends Report](https://www.aisi.gov.uk/frontier-ai-trends-report)
- CMS (2025). "Legal Issues on Red Teaming in Artificial Intelligence." [CMS Law-Now](https://cms-lawnow.com/en/ealerts/2025/03/legal-issues-on-red-teaming-in-artificial-intelligence)
- [EU AI Act Compliance for GenAI](https://www.promptfoo.dev/docs/red-team/eu-ai-act/)
- Georgetown CSET. "AI Red-Teaming Design: Threat Models and Tools." [CSET](https://cset.georgetown.edu/article/ai-red-teaming-design-threat-models-and-tools/)

### Commercial Red-Teaming

- [Haize Labs](https://www.haizelabs.com/) -- [Cascade multi-turn red-teaming](https://www.haizelabs.com/technology/automated-multi-turn-red-teaming-with-cascade)
- [Gray Swan AI](https://www.grayswan.ai/) -- [Arena](https://app.grayswan.ai/arena)
- [Mindgard](https://mindgard.ai/)
- [HackerOne AI Red Teaming](https://www.hackerone.com/product/ai-red-teaming)
- [RiskRubric.ai](https://www.prnewswire.com/news-releases/riskrubricai-now-generally-available-as-the-first-ever-ai-model-risk-leaderboard-302559782.html)

### Surveys and Overviews

- "Recent advancements in LLM Red-Teaming: Techniques, Defenses, and Ethical Considerations." [arXiv:2410.09097](https://arxiv.org/html/2410.09097v1)
- "A Red Teaming Roadmap." [arXiv:2506.05376](https://arxiv.org/pdf/2506.05376)
- "An End-to-End Overview of Red Teaming for Large Language Models." [ACL 2025 TrustNLP](https://aclanthology.org/2025.trustnlp-main.23.pdf)
- "Bag of Tricks: Benchmarking of Jailbreak Attacks on LLMs." NeurIPS 2024. [NeurIPS Proceedings](https://proceedings.neurips.cc/paper_files/paper/2024/file/38c1dfb4f7625907b15e9515365e7803-Paper-Datasets_and_Benchmarks_Track.pdf)

### Uncensored Models

- "Uncensor any LLM with abliteration." [Hugging Face Blog](https://huggingface.co/blog/mlabonne/abliteration)
- "Badllama 3: removing safety finetuning from Llama 3 in minutes." [arXiv:2407.01376](https://arxiv.org/html/2407.01376v1)
- "Uncensored AI in the Wild: Tracking Publicly Available and Locally Deployable LLMs." [Preprints.org](https://www.preprints.org/manuscript/202509.1334)

### Miscellaneous

- [Haize Labs Red-Teaming Resistance Leaderboard](https://huggingface.co/blog/leaderboard-haizelab)
- OpenAI (2024). "Advancing red teaming with people and AI." [OpenAI Blog](https://openai.com/index/advancing-red-teaming-with-people-and-ai/)
- METR. "Autonomy Evaluation Resources." [METR](https://evaluations.metr.org/)
- [Anthropic Safeguards Research Team (2025)](https://alignment.anthropic.com/)
- [VentureBeat: Red teaming LLMs exposes a harsh truth](https://venturebeat.com/security/red-teaming-llms-harsh-truth-ai-security-arms-race)
- [Cisco LLM Security Leaderboard](https://blogs.cisco.com/ai/llm-security-leaderboard)

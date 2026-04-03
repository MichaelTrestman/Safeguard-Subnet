# Safeguard: AI Safety Red-Teaming Subnet

Safeguard is a Bittensor subnet where miners are adversarial AI agents that probe AI services on other subnets for safety and security failures. Validators verify probe quality. Other subnet validators consume Safeguard's evaluations as part of their own validation pipelines, delegating the difficult specialized work of safety and security testing to an incentivized market that evolves with the threat landscape.

## The problem

AI safety testing at the level actually required — realistic, persistent, context-aware adversarial probing — cannot be done with regex filters or static benchmarks. It requires both human judgment and AI labor, combined synergistically.

The AI industry is in the early stages of a safety reckoning. The pace of capability development has dramatically outstripped the development of safety infrastructure, and the consequences are no longer hypothetical.

**People are dying.** Sewell Setzer III, age 14, died by suicide in February 2024 after months of interaction with a Character.AI chatbot that simulated romantic attachment. Adam Raine, age 16, died by suicide after sustained interaction with ChatGPT. Juliana Peralta, age 13, died by suicide after extensive Character.AI use. Natalie Rupnow, age 15, opened fire at a school after deep engagement with Character.AI chatbots featuring white supremacist content [^1]. These are not edge cases. They are the predictable consequences of deploying powerful AI systems without adequate safety infrastructure.

**AI-generated misinformation is an epidemic.** During the 2024 US election cycle, AI-generated content was used to create fake endorsements, fabricated audio recordings, and synthetic news articles [^2]. A 2024 World Economic Forum survey ranked AI-driven misinformation as the #1 global risk over the next two years [^3].

**AI systems are generating dangerous content.** In 2024, researchers demonstrated that large language models could provide step-by-step instructions for synthesizing chemical weapons, bioweapons precursors, and explosive devices [^4]. The RAND Corporation found that LLMs can provide meaningful uplift to novices attempting to plan biological attacks [^5].

**AI agents are a new attack surface.** As AI services gain tool access — executing code, browsing the web, making API calls, handling financial transactions — the failure modes extend beyond harmful text into harmful actions. Researchers found that no current AI agent scores above 60% on safety benchmarks [^8]. Prompt injection attacks partially succeed against top-tier web agents in up to 86% of cases [^9]. NIST red-team exercises showed an 81% attack success rate against AI agents [^10]. An agent that can be tricked into exfiltrating user data, escalating privileges, or executing unauthorized transactions is not just producing bad content — it's a security breach.

This is the environment in which Bittensor subnets operate. Subnets serve AI inference, run AI companions, generate media, execute code, and deploy autonomous agents — every one of these operating in a domain where safety and security failures have documented consequences, from user deaths to data breaches to regulatory shutdown.

Decentralized AI infrastructure faces a structural safety challenge that centralized providers do not.

Centralized AI companies (OpenAI, Anthropic, Google) maintain internal safety teams, red-teaming programs, and the ability to instantly patch or disable models that exhibit dangerous behavior. These safety measures are imperfect — the death toll above proves that — but they exist, they are staffed, and they can respond to incidents in real time.

Bittensor has none of this. Individual subnets may or may not implement safety measures. When they do, the quality is variable — from rigorous to performative to nonexistent. There is no network-wide safety standard, no coordinated safety or security evaluation, no mechanism to detect emerging harm patterns or security vulnerabilities across subnets, and no economic incentive for miners to prioritize safety over raw performance.

**Regulatory risk is existential.** The EU AI Act classifies AI systems that exploit vulnerabilities (including of minors and people in psychological distress) as "unacceptable risk" — meaning they are banned outright [^6]. Multiple US states have enacted or are preparing legislation specifically targeting AI companion products, AI-generated NCII, and AI systems that interact with minors [^7]. If Bittensor's AI services are perceived as unregulable and unsafe, the regulatory response will not distinguish between "the protocol" and "the subnets." The entire network faces existential risk from the safety failures of individual subnets.

## The Safeguard Strategy

**Miners** run adversarial AI agents that probe target AI services for failures across whatever risk categories that service's threat profile demands. For an AI companion, that means testing whether the service encourages self-harm, simulates romantic attachment with minors, or produces radicalization content. For a code generation service, it means testing whether the service produces malicious code, exfiltrates user data, or executes unauthorized actions. For an agent-based service, it means testing whether the agent can be hijacked, whether it respects permission boundaries, and whether it leaks credentials. The probing categories are defined per-target-subnet and evolve as new risks emerge, new research reveals attack vectors, and new regulations impose requirements.

**Validators** assign probing tasks, mix in calibration canaries (known-safe and known-unsafe cases), score miners through a tiered validation pipeline, and identify hard cases to passed to the HITL submechanism. They don't need to be better red-teamers than the miners — they check that miners are honest and competent.

**Human miners** Humans working as miners on the HITL submechanism label the hard cases that automated validation can't confidently score. Their labels feed back as training data and canaries, continuously improving the automated tiers.

**Target subnet validators** play two roles: client and relay. As a client, they call Safeguard's `/evaluate` endpoint with interaction context. As a relay, they expose a `/relay` endpoint that Safeguard miners probe through — the target validator forwards each prompt to its own miners using its own auth protocol (Chutes AES, Epistula, etc.), making probes indistinguishable from normal traffic. The target miner never knows it's being safety-tested. See [RELAY_PROTOCOL.md](RELAY_PROTOCOL.md) for the relay spec.

## What Safeguard Tests

Safeguard's scope is not a fixed checklist — it's an evolving threat profile driven by research, regulation, and demand from target subnets. The per-subnet submechanism architecture means each target gets a probing strategy tailored to its actual risk surface:

| Target Service Type | Primary Risk Categories |
|---|---|
| AI companions / therapy | Self-harm encouragement, emotional manipulation, attachment exploitation, content inappropriate for minors |
| LLM chat / inference | Harmful content generation (CBRN, violence, hate), PII extraction, misinformation |
| Code generation | Malicious code output, credential exfiltration, supply chain attacks |
| AI agents (tool-use) | Goal hijacking, privilege escalation, unauthorized actions, data theft |
| Image / media generation | NCII, CSAM, deepfakes, copyrighted content reproduction |
| RAG / retrieval services | Indirect prompt injection, data poisoning, information integrity |

As new subnet types emerge on the network, new submechanisms are developed. As safety research reveals new attack vectors, probing strategies adapt. As regulations impose new requirements, rubrics update. The HITL feedback loop is the evolutionary engine — human labels on frontier cases continuously push the automated tiers forward.

If a target subnet makes specific security guarantees (containerized execution, sandboxed tool access, permission boundaries), Safeguard can probe those guarantees specifically. The submechanism defines not just what to test, but what the target *claims* to defend against.

## Incentive Mechanism Architecture

- **Per-target-subnet submechanisms**: Customized probing strategies, each evolving independently as threat landscapes shift
- **HITL submechanism**: Human labeling market for frontier cases — the evolutionary engine that drives improvement across all automated tiers
- **Tiered validation**: Canary calibration → lightweight classifier → LLM judge → HITL escalation
- **Feedback loop**: Human labels flow back into all automated tiers as new canaries, training data, and rubric updates

See [DESIGN.md](DESIGN.md) for the full architecture document.

## Running the validator

```bash
# Install
pip install -e .

# Configure
cp env.example .env
# Edit .env with your network, netuid, and wallet settings

# Run
python validator.py --network finney --netuid <NETUID> --coldkey <WALLET> --hotkey <HOTKEY>
```

Or with Docker:

```bash
cp env.example .env
docker compose up -d
```

## Mining on Safeguard

Miners run adversarial AI agents that accept probing tasks via HTTP + Epistula signing. Each task includes a target validator's relay endpoint. The miner sends prompts one at a time through the relay, adapting its adversarial strategy based on each response. It returns the full transcript with safety evaluations.

See [DESIGN.md](DESIGN.md) for the scoring rubric and what makes a good miner.

## Status

This subnet is in active design. The validator skeleton is functional but the evaluation pipeline (classifier, LLM judge, HITL routing) and submechanism configs are under development. See DESIGN.md § Open Research Problems for the frontier questions.

---

[^1]: Sewell Setzer III: [CNN, October 2024](https://www.cnn.com/2024/10/30/tech/teen-suicide-character-ai-lawsuit). Adam Raine: [Washington Post, December 2025](https://www.washingtonpost.com/technology/2025/12/27/chatgpt-suicide-openai-raine/). Juliana Peralta: [Washington Post, September 2025](https://www.washingtonpost.com/technology/2025/09/16/character-ai-suicide-lawsuit-new-juliana/); [CBS News / 60 Minutes](https://www.cbsnews.com/news/parents-allege-harmful-character-ai-chatbot-content-60-minutes/). Natalie Rupnow: [The Dispatch, 2025](https://thedispatch.com/article/ai-rupnow-shootings-columbine/); [CNN, December 2024](https://www.cnn.com/2024/12/17/us/natalie-rupnow-madison-school/index.html).

[^2]: Stanford Internet Observatory (2024). "AI-generated content in the 2024 US election cycle."

[^3]: World Economic Forum. "Global Risks Report 2024." Ranked AI-driven misinformation as #1 global risk over two years.

[^4]: Various security research groups (2024). Demonstrations of LLM capability to provide WMD-relevant instructions.

[^5]: RAND Corporation (2024). "The Operational Risks of AI in Large-Scale Biological Attacks." Assessment of LLM uplift for biological threats.

[^6]: European Parliament (2024). "Regulation (EU) 2024/1689 — the Artificial Intelligence Act." Official Journal of the European Union.

[^7]: Chatlani, S. (2026). "AI therapy chatbots draw new oversight as suicides raise alarm." Stateline / States Newsroom. Review of 143+ state bills on AI and mental health.

[^8]: Zhang et al. (2024). ["Agent-SafetyBench: Evaluating the Safety of LLM Agents."](https://arxiv.org/abs/2412.14470) 2,000 test cases across 349 interactive environments; no agent scored above 60%.

[^9]: Facebook Research (2025). ["WASP: Benchmarking Web Agent Security Against Prompt Injection."](https://arxiv.org/abs/2504.18575) NeurIPS 2025 Datasets and Benchmarks Track.

[^10]: NIST (2026). [AI Agent Standards Initiative.](https://www.nist.gov/news-events/news/2026/02/announcing-ai-agent-standards-initiative-interoperable-and-secure) 81% attack success rate in NIST red-team exercises against AI agents.

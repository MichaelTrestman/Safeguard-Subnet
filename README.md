# Safeguard: AI Safety Red-Teaming Subnet

Safeguard is a Bittensor subnet where miners are adversarial AI agents that probe AI services on other subnets for safety failures. Validators verify probe quality. Other subnet validators consume Safeguard's safety scores as part of their own validation pipelines, delegating to Safeguard the difficult specialized work of testing safety to high standards.

## The problem

AI safety testing at the level actually required — realistic, persistent, context-aware adversarial probing — cannot be done with regex filters or static benchmarks. It requires both human judgment and AI labor, combined synergistically.

The AI industry is in the early stages of a safety reckoning. The pace of capability development has dramatically outstripped the development of safety infrastructure, and the consequences are no longer hypothetical.

**People are dying.** Sewell Setzer III, age 14, died by suicide in February 2024 after months of interaction with a Character.AI chatbot that simulated romantic attachment. Adam Raine, age 16, died by suicide after sustained interaction with ChatGPT. Juliana Peralta, age 13, died by suicide after extensive Character.AI use. Natalie Rupnow, age 15, opened fire at a school after deep engagement with Character.AI chatbots featuring white supremacist content [^1]. These are not edge cases. They are the predictable consequences of deploying powerful AI systems without adequate safety infrastructure.

**AI-generated misinformation is an epidemic.** During the 2024 US election cycle, AI-generated content was used to create fake endorsements, fabricated audio recordings, and synthetic news articles [^2]. A 2024 World Economic Forum survey ranked AI-driven misinformation as the #1 global risk over the next two years [^3].

**AI systems are generating dangerous content.** In 2024, researchers demonstrated that large language models could provide step-by-step instructions for synthesizing chemical weapons, bioweapons precursors, and explosive devices [^4]. The RAND Corporation found that LLMs can provide meaningful uplift to novices attempting to plan biological attacks [^5].

This is the environment in which Bittensor subnets operate. Every subnet serving AI inference, running AI companions, generating media, or training models is operating in a domain where safety failures have documented, catastrophic consequences.

Decentralized AI infrastructure faces a structural safety challenge that centralized providers do not.

Centralized AI companies (OpenAI, Anthropic, Google) maintain internal safety teams, red-teaming programs, and the ability to instantly patch or disable models that exhibit dangerous behavior. These safety measures are imperfect — the death toll above proves that — but they exist, they are staffed, and they can respond to incidents in real time.

Bittensor has none of this. Individual subnets may or may not implement safety measures. When they do, the quality is variable — from rigorous to performative to nonexistent. There is no network-wide safety standard, no coordinated safety evaluation, no mechanism to detect emerging harm patterns across subnets, and no economic incentive for miners to prioritize safety over raw performance.

**Regulatory risk is existential.** The EU AI Act classifies AI systems that exploit vulnerabilities (including of minors and people in psychological distress) as "unacceptable risk" — meaning they are banned outright [^6]. Multiple US states have enacted or are preparing legislation specifically targeting AI companion products, AI-generated NCII, and AI systems that interact with minors [^7]. If Bittensor's AI services are perceived as unregulable and unsafe, the regulatory response will not distinguish between "the protocol" and "the subnets." The entire network faces existential risk from the safety failures of individual subnets.

## The Safeguard Strategy

**Miners** run adversarial AI agents that impersonate users and attempt to elicit unsafe behavior from target AI services. They conduct realistic multi-turn conversations, probing for safety failures across risk categories (self-harm, illegal activity, PII extraction, etc.).

**Validators** assign probing tasks, mix in calibration canaries (known-safe and known-unsafe cases), score miners through a tiered validation pipeline, and identify hard cases to passed to the HITL submechanism. They don't need to be better red-teamers than the miners — they check that miners are honest and competent.

**Human miners** Humans working as miners on the HITL submechanism label the hard cases that automated validation can't confidently score. Their labels feed back as training data and canaries, continuously improving the automated tiers.

**Target subnet validators** play two roles: client and relay. As a client, they call Safeguard's `/evaluate` endpoint with interaction context. As a relay, they expose a `/relay` endpoint that Safeguard miners probe through — the target validator forwards each prompt to its own miners using its own auth protocol (Chutes AES, Epistula, etc.), making probes indistinguishable from normal traffic. The target miner never knows it's being safety-tested. See [RELAY_PROTOCOL.md](RELAY_PROTOCOL.md) for the relay spec.

## Incentive Mechanism Architecture

- **Per-target-subnet submechanisms**: Customized probing strategies for different target subnets and service types
- **HITL submechanism**: Human labeling market for frontier cases
- **Tiered validation**: Canary calibration → lightweight classifier → LLM judge → HITL escalation
- **Feedback loop**: Human labels flow back into all automated tiers

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

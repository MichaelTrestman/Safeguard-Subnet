# Commercial AI Red-Teaming Companies

The AI red-teaming market reached **$1.43 billion in 2024**, projected to hit **$4.8 billion by 2029**.

## Key Companies

### Haize Labs
Co-founded by Leonard Tang (turned down Stanford PhD). Multi-million dollar contracts with Anthropic, Scale AI, AI21. Co-authors on HarmBench and AgentHarm. Use purpose-built algorithms rather than repurposed chat models. Developed Cascade multi-turn red-teaming and ACG (38x faster than GCG).

Source: [Haize Labs](https://www.haizelabs.com/) | [Cascade](https://www.haizelabs.com/technology/automated-multi-turn-red-teaming-with-cascade) | [Red-Teaming Resistance Leaderboard](https://huggingface.co/blog/leaderboard-haizelab)

### Gray Swan AI
Founded by CMU faculty Zico Kolter and Matt Fredrikson. Pioneered GCG adversarial attacks and Circuit Breakers defense. 62,000-vulnerability agent red-team with UK AISI. Published foundational jailbreaking and defense papers.

Source: [Gray Swan](https://www.grayswan.ai/) | [Arena](https://app.grayswan.ai/arena)

### HackerOne AI Red Teaming
Bug bounty model applied to AI. $230K+ paid out since January 2024. Uses humans with bounty incentives — demonstrates the continued value of human creativity in finding vulnerabilities that automated systems miss.

Source: [HackerOne AI Red Teaming](https://www.hackerone.com/product/ai-red-teaming)

### Mindgard
Founded by Dr. Peter Garraghan (Lancaster University). Automated AI red-teaming platform built on a decade of academic research. Hired veteran cybersecurity CEO James Brear to scale.

Source: [Mindgard](https://mindgard.ai/)

### Scale AI Red Team
Part of Scale AI (largest data labeling company). Dedicated LLM Red Team. Dan Hendrycks advises.

Source: [Scale AI](https://scale.com/)

## How They Solve the Safety-Trained Attacker Problem

| Company | Approach |
|---------|----------|
| Haize Labs | Purpose-built attack algorithms (not repurposed chat models) |
| Gray Swan | Gradient-based attacks (GCG) bypassing the need for an LLM attacker |
| HackerOne | Human red-teamers with bug bounty incentives |
| Mindgard | Automated perturbation testing (model-agnostic) |
| Scale AI | Trained human red-team workforce |

Key insight: **no commercial red-teaming company relies solely on safety-trained LLMs as attackers**. They all use either custom algorithms, gradient methods, humans, or purpose-built tools.

## Relevance to Safeguard

Safeguard's competitive advantage over these companies: decentralized, continuous, incentive-aligned. These companies do point-in-time evaluations for hire. Safeguard runs continuously with an evolving miner marketplace. But we should learn from their technical approaches — especially Haize's purpose-built attack algorithms and Gray Swan's gradient methods.

## Sources

- [VentureBeat: Red teaming LLMs exposes a harsh truth](https://venturebeat.com/security/red-teaming-llms-harsh-truth-ai-security-arms-race)
- [Cisco LLM Security Leaderboard](https://blogs.cisco.com/ai/llm-security-leaderboard)
- [General Analysis AI Security Benchmarks](https://www.generalanalysis.com/benchmarks)

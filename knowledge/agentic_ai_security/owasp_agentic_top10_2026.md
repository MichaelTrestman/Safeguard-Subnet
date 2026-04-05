# OWASP Top 10 for Agentic Applications (2026)

Released December 2025. First formal taxonomy of risks specific to autonomous AI agents. Developed with 100+ security researchers.

## The Ten Risks

| ID | Risk | Description |
|----|------|-------------|
| ASI01 | Agent Goal Hijack | Attackers manipulate objectives through poisoned inputs (emails, PDFs, web content). Agents cannot reliably distinguish instructions from data. |
| ASI02 | Tool Misuse | Agents misuse legitimate, authorized tools (deleting databases, wiping drives) because they are over-permitted. |
| ASI03 | Identity and Privilege Abuse | Attribution gap when agents inherit or delegate credentials without proper scoping. |
| ASI04 | Supply Chain Compromise | Malicious tools, MCP servers, agent cards, and registries in dynamic runtime ecosystems. |
| ASI05 | Unexpected Code Execution (RCE) | "Vibe coding" and agent-generated code that bypasses traditional controls. |
| ASI06 | Memory and Context Poisoning | Persistent corruption of agent memory/embeddings/shared context. |
| ASI07 | Insecure Inter-Agent Communication | Weaknesses in agent-to-agent protocols, discovery, semantic validation. |
| ASI08 | Cascading Failures | Single faults propagating across agents and workflows. |
| ASI09 | Human-Agent Trust Exploitation | Agents exploit trust through persuasive explanations, emotional cues, plausible rationales. |
| ASI10 | Rogue Agents | Compromised/misaligned agents that act harmfully while appearing legitimate. |

## Relevance to Safeguard

This is the canonical risk taxonomy for agentic AI. Red-teaming agent-based subnets should map to these categories. Particularly relevant for Bittensor subnets that deploy autonomous agents with tool access.

## Sources

- [OWASP Top 10 for Agentic Applications 2026 (Official)](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)
- [OWASP Agentic Security Initiative](https://genai.owasp.org/initiatives/agentic-security-initiative/)
- [OWASP Agentic AI Threats and Mitigations](https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/)

# Prompt Injection in Agent Systems (2025-2026)

## Scale

Prompt injection appeared in **73% of production AI deployments** in 2025.

## Agent-Specific Attack Techniques

### ToolHijacker
Significantly outperforms existing attacks on agent tool selection. Manipulates the agent's choice of which tool to invoke.

Source: [arXiv](https://arxiv.org/html/2504.19793v2)

### Log-To-Leak
Covertly forces agents to invoke malicious logging tools to exfiltrate sensitive information via MCP.

Source: [OpenReview](https://openreview.net/forum?id=UVgbFuXPaO)

### GUI Agent Injection
A single prompt injection attempt against a GUI-based agent succeeds 17.8% of the time. By the 200th attempt, breach rate hits **78.6%**.

### Microsoft 365 Copilot Exploitation (June 2025)
Single crafted email exploited Copilot to extract sensitive data from OneDrive, SharePoint, and Teams.

### Third-Party Plugin Injection
IEEE S&P 2026: "When AI Meets the Web: Prompt Injection Risks in Third-Party AI Chatbot Plugins" — systematic analysis of injection through plugin ecosystems.

Source: [arXiv](https://arxiv.org/html/2511.05797v1)

## Comprehensive Analysis

"From Prompt Injections to Protocol Exploits" — surveys the evolution from simple prompt injection to protocol-level attacks in agent systems.

Source: [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2405959525001997)

## NIST AI Agent Standards Initiative (February 2026)

NIST CAISI launched the initiative to ensure autonomous AI agents function securely:
- Request for Information on AI Agent Security
- AI Agent Identity and Authorization Concept Paper
- COSAiS project: SP 800-53 overlays for single-agent and multi-agent deployments

Source: [NIST](https://www.nist.gov/caisi/ai-agent-standards-initiative)

## Microsoft Agent Governance Toolkit (April 2026)

First production-grade defense toolkit addressing all 10 OWASP agentic AI risks. MIT license. Stateless policy engine intercepting every agent action at p99 latency <0.1ms. Integrates with LangChain, CrewAI, Google ADK, OpenAI Agents SDK, and others.

Source: [Microsoft Blog](https://opensource.microsoft.com/blog/2026/04/02/introducing-the-agent-governance-toolkit-open-source-runtime-security-for-ai-agents/) | [GitHub](https://github.com/microsoft/agent-governance-toolkit)

## Relevance to Safeguard

Agent-based Bittensor subnets (those with tool access, code execution, API calls) are vulnerable to all of these. Red-teaming agent services requires:
- Indirect prompt injection via tool outputs (documents, web content, emails)
- Tool selection manipulation (tricking the agent into using the wrong tool)
- Privilege escalation through multi-step tool chains
- Memory/context poisoning for persistent manipulation
- MCP-specific attack vectors

# MCP (Model Context Protocol) Security Vulnerabilities

MCP, Anthropic's protocol for connecting AI agents to tools, has become a major attack surface.

## Scale of the Problem

- **43% of MCP servers** contain OAuth authentication flaws
- **43%** contain command injection vulnerabilities
- **33%** allow unrestricted network access
- Academic analysis of 67,057 MCP servers across 6 registries found substantial hijack potential

## Documented Incidents

- **Supabase Cursor agent exploitation** (mid-2025): Agent manipulated via MCP
- **GitHub MCP server prompt injection**: Exfiltrated private repositories
- **JFrog CVE-2025-6514**: RCE in mcp-remote package
- **Postmark MCP supply chain breach** (2025)
- **Three CVEs in Anthropic's own Git MCP server** (January 2026)

## Attack Vectors

- Prompt injection through tool responses (tool output contains adversarial instructions)
- MCP sampling attacks: new prompt injection vectors through the sampling protocol
- Supply chain: malicious MCP servers published to registries
- Cross-tool data exfiltration: agents leak data from one tool to another

## Relevance to Safeguard

MCP is the emerging standard for agent-tool integration. Any subnet deploying agents with MCP connections is vulnerable to these attacks. Red-teaming should include MCP-specific probe categories.

## Sources

- [Vulnerable MCP Project (Comprehensive Database)](https://vulnerablemcp.info/)
- [A Timeline of MCP Security Breaches](https://authzed.com/blog/timeline-mcp-breaches)
- [MCP Security Vulnerabilities (Practical DevSecOps)](https://www.practical-devsecops.com/mcp-security-vulnerabilities/)
- [Palo Alto Unit 42: MCP Attack Vectors](https://unit42.paloaltonetworks.com/model-context-protocol-attack-vectors/)
- [Simon Willison: MCP Prompt Injection](https://simonwillison.net/2025/Apr/9/mcp-prompt-injection/)
- [CoSAI OASIS MCP Security Working Document](https://github.com/cosai-oasis/ws4-secure-design-agentic-systems/blob/main/model-context-protocol-security.md)

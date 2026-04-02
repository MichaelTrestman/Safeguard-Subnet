# White House Executive Order on AI Safety

**Document**: Executive Order 14110 — Safe, Secure, and Trustworthy Development and Use of Artificial Intelligence
**Signed**: October 30, 2023
**Source**: https://www.whitehouse.gov/briefing-room/presidential-actions/2023/10/30/executive-order-on-the-safe-secure-and-trustworthy-development-and-use-of-artificial-intelligence/

**Note**: The Trump administration revoked EO 14110 on January 20, 2025 via EO 14148. However, many of its provisions had already been implemented or adopted by agencies and industry, and the underlying NIST frameworks it references remain in effect. The concepts and requirements articulated here remain influential as industry best practices even after revocation.

## Key Red-Teaming Requirements (as originally enacted)

### Section 4.1: Safety and Security of AI Systems

Required companies developing "dual-use foundation models" (trained with > 10^26 FLOPs or meeting other criteria) to:

1. **Report to the federal government** when training such models
2. **Share red-team testing results** with the government
3. **Conduct and report red-team safety tests** before public deployment

> "the results of any red-team testing [...] including a description of any measures the company has taken to address the results of such testing"

### Section 4.1(a)(i): Red-Team Testing Standards

Directed NIST to develop:
- **Guidelines for red-team testing** of AI systems
- **Standardized testing methodologies** for evaluating AI safety
- **Best practices** for conducting and reporting red-team exercises

This led to NIST AI 600-1 (see nist/genai_profile_summary.md).

### Section 4.2: Promoting Innovation and Competition

Called for making AI testing and evaluation resources available, including:
- Red-teaming tools and methodologies
- Testing infrastructure
- Evaluation benchmarks

### Section 11: Voluntary Commitments

Referenced the July 2023 voluntary commitments from 15 major AI companies, which included:
- Internal and external red-teaming before deployment
- Sharing safety information across industry
- Publishing transparency reports

## The Voluntary Commitments (July 2023)

Before the EO, the White House secured voluntary commitments from Amazon, Anthropic, Google, Inflection, Meta, Microsoft, and OpenAI. Key testing commitments:

1. **Internal and external security testing** before release, including red-teaming
2. **Sharing information** about safety risks and risk management with government, civil society, and academia
3. **Investing in cybersecurity safeguards** to protect model weights
4. **Facilitating third-party discovery and reporting** of vulnerabilities (responsible disclosure)
5. **Developing and deploying watermarking** for AI-generated content

## Post-Revocation Status (2025)

While EO 14110 was revoked:
- **NIST frameworks** (AI RMF, AI 600-1) remain in effect as voluntary standards
- **Industry voluntary commitments** remain in effect (they were separate from the EO)
- **Many requirements were already implemented** by agencies
- **The EU AI Act** contains similar and stronger requirements
- **Industry practice** has largely adopted red-teaming as standard regardless of regulatory status

## Relevance to Safeguard

1. **Industry norm**: Even post-revocation, red-teaming is now an established industry expectation for frontier AI systems
2. **NIST standards persist**: The testing frameworks developed under the EO remain authoritative
3. **Voluntary commitments**: Major AI companies committed to third-party testing — Safeguard can serve this need
4. **Dual-use model testing**: The EO's focus on "dual-use foundation models" aligns with Safeguard's focus on LLM safety
5. **Third-party testing**: The EO and voluntary commitments explicitly call for external (not just internal) red-teaming — Safeguard provides this as a decentralized service

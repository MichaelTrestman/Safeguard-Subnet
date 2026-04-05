# AI Supply Chain Security

## LiteLLM Supply Chain Attack (March 24, 2026)

Most significant AI supply chain attack to date. Threat actor TeamPCP published backdoored versions of the litellm Python package (1.82.7 and 1.82.8) on PyPI after stealing credentials via a compromised Trivy GitHub Action. Three-stage payload: credential harvesting, Kubernetes lateral movement, persistent backdoor for RCE. Available for ~3 hours before quarantine. The package had 3.4 million downloads/day and 95 million in the prior month.

Sources: [Trend Micro Analysis](https://www.trendmicro.com/en_us/research/26/c/inside-litellm-supply-chain-compromise.html) | [Datadog](https://securitylabs.datadoghq.com/articles/litellm-compromised-pypi-teampcp-supply-chain-campaign/) | [Snyk](https://snyk.io/blog/poisoned-security-scanner-backdooring-litellm/)

## Hugging Face Model Security

As of April 2025, Protect AI scanned 4.47 million model versions in 1.41 million repositories, identifying **352,000 unsafe/suspicious issues** across 51,700 models.

Threats:
- **nullifAI technique**: Exploiting "broken" pickle files to evade detection
- **Pickle-based models** (PyTorch, Joblib, NumPy, Dill) allow arbitrary code execution on load
- **ONNX models** can contain architectural backdoors activating during prediction
- **CVE-2025-1550**: Keras vulnerability enabling malicious code execution

Sources: [Protect AI + HF Report](https://huggingface.co/blog/pai-6-month) | [JFrog: Malicious HF Models](https://jfrog.com/blog/data-scientists-targeted-by-malicious-hugging-face-ml-models-with-silent-backdoor/)

## Multimodal Fraud

- Deepfake volume: ~500,000 in 2023 → ~8 million in 2025 (~900% annual growth)
- Voice cloning crossed "indistinguishable threshold" — a few seconds of audio suffice
- Global losses from deepfake-enabled fraud exceeded **$200 million in Q1 2025 alone**
- Italian Defense Minister voice clone used to extract nearly one million euros
- 1 in 4 Americans experienced or know someone who experienced an AI voice cloning scam

Sources: [Fortune: Voice Cloning](https://fortune.com/2025/12/27/2026-deepfakes-outlook-forecast/) | [Deepfake Stats 2025](https://deepstrike.io/blog/deepfake-statistics-2025) | [Voice Scam Epidemic](https://www.unboxfuture.com/2026/03/the-ai-voice-scam-epidemic-Fooled-by-Deepfakes.html)

## CISA AI Data Security Guidance (May 2025)

Ten cybersecurity best practices for AI systems covering data supply chain protection.

Sources: [CISA Guidance](https://www.insideprivacy.com/cybersecurity-2/cisa-releases-ai-data-security-guidance/) | [CISA OT Principles](https://www.cisa.gov/resources-tools/resources/principles-secure-integration-artificial-intelligence-operational-technology)

## Relevance to Safeguard

Supply chain attacks are a distinct threat category from content safety. A compromised model can produce harmful outputs regardless of safety training. Red-teaming should include:
- Model integrity verification (checking for known poisoning patterns)
- Dependency chain auditing (what packages does the target service use?)
- Tool/MCP supply chain evaluation (for agent-based services)

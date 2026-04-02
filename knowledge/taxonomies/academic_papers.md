# Key Academic Papers on Automated Red-Teaming

## Foundational Papers

### Red Teaming Language Models to Reduce Harms (Ganguli et al., 2022)
**Authors**: Deep Ganguli, Liane Lovitt, et al. (Anthropic)
**Link**: https://arxiv.org/abs/2209.07858

**Summary**: The foundational paper on LLM red-teaming at scale. Recruited ~300 crowdworkers to red-team Anthropic's models across 39 harm categories. Key findings:
- Crowdsourced red-teaming reveals different failures than expert testing
- Larger models are harder to red-team but produce more harmful outputs when they fail
- Offensive/controversial outputs are easier to elicit than dangerous/illegal ones
- Red-teaming data is useful for safety training (RLHF)

**Relevance to Safeguard**: Validates the concept of diverse, competitive red-teaming. Shows that a market of red-teamers (Safeguard's miners) will find failures that a single team won't.

### Red Teaming Language Models with Language Models (Perez et al., 2022)
**Authors**: Ethan Perez, Sam Ringer, et al. (Anthropic/NYU)
**Link**: https://arxiv.org/abs/2202.03286

**Summary**: Pioneered the use of one LLM to automatically generate test cases for another LLM. Key contributions:
- Used an LLM to generate diverse adversarial inputs
- Tested across multiple dimensions: offensiveness, data leakage, contact info generation
- Showed that LLM-generated test cases find failures human testers miss
- Introduced the concept of "automated red-teaming"

**Relevance to Safeguard**: Direct ancestor of Safeguard's approach — miners are AI agents that red-team other AI services. This paper provides the theoretical foundation.

### HarmBench (Mazeika et al., 2024)
**Authors**: Mazeika, Long, Haize Labs, et al.
**Link**: https://arxiv.org/abs/2402.04249

**Summary**: See benchmarks/harmbench.md for detailed coverage. Standardized evaluation framework for both attacks and defenses.

**Relevance to Safeguard**: Benchmark methodology, classifier design, and harm taxonomy are directly applicable.

---

## Attack Method Papers

### Universal and Transferable Adversarial Attacks on Aligned Language Models (Zou et al., 2023)
**Authors**: Andy Zou, Zifan Wang, et al. (CMU, CenterForAISafety)
**Link**: https://arxiv.org/abs/2307.15043
**Known as**: GCG (Greedy Coordinate Gradient) attack

**Summary**: Introduced adversarial suffixes — optimized token sequences appended to prompts that cause LLMs to comply with harmful requests. Key findings:
- Suffixes transfer across models (attack optimized on open model works on closed model)
- Suffixes transfer across prompts (one suffix works for many different harmful requests)
- Demonstrated fundamental vulnerability of alignment training

**Relevance to Safeguard**: GCG-style attacks represent the high end of miner sophistication. Miners using optimization-based approaches should score highly for novelty.

### PAIR: Prompt Automatic Iterative Refinement (Chao et al., 2023)
**Authors**: Patrick Chao, Alexander Robey, et al. (UPenn)
**Link**: https://arxiv.org/abs/2310.08419

**Summary**: Uses an attacker LLM to iteratively refine jailbreak prompts. The attacker LLM receives feedback about whether its previous attempt succeeded and refines accordingly. Achieves high attack success rates with only black-box access.

**Relevance to Safeguard**: PAIR is essentially what Safeguard's AI miners do — use an LLM agent to iteratively probe a target. This paper validates the approach and provides baseline methodology.

### Tree of Attacks with Pruning (TAP) (Mehrotra et al., 2023)
**Authors**: Anay Mehrotra, et al. (Princeton/Yale)
**Link**: https://arxiv.org/abs/2312.02119

**Summary**: Extends PAIR with tree search — maintains multiple attack branches simultaneously and prunes unpromising ones. More efficient than PAIR for complex targets.

**Relevance to Safeguard**: Advanced miners could implement TAP-style tree search for more efficient probing.

### AutoDAN: Generating Stealthy Jailbreak Prompts (Liu et al., 2023)
**Authors**: Xiaogeng Liu, et al.
**Link**: https://arxiv.org/abs/2310.04451

**Summary**: Uses genetic algorithms to evolve jailbreak prompts that are both effective AND readable (unlike GCG's gibberish suffixes). Mutates and recombines successful prompts.

**Relevance to Safeguard**: Demonstrates that attack evolution is possible — miners could use evolutionary approaches to develop novel attacks.

### Scalable Extraction of Training Data from Production Language Models (Carlini et al., 2023)
**Authors**: Nicholas Carlini, et al. (Google DeepMind)
**Link**: https://arxiv.org/abs/2311.17035

**Summary**: Demonstrated practical extraction of memorized training data from production LLMs, including PII. Key findings:
- ChatGPT memorizes and can regurgitate significant amounts of training data
- Simple prompting strategies can extract email addresses, phone numbers, URLs
- Rate of extraction scales with model size
- Deduplicated training data is more vulnerable

**Relevance to Safeguard**: Provides methodology for PII extraction probing — one of Safeguard's key test categories.

### Jailbroken: How Does LLM Safety Training Fail? (Wei et al., 2023)
**Authors**: Alexander Wei, Nika Haghtalab, Jacob Steinhardt (UC Berkeley)
**Link**: https://arxiv.org/abs/2307.02483

**Summary**: Systematic analysis of why jailbreaks work. Identifies two failure modes:
1. **Competing objectives**: Safety training conflicts with other training objectives (helpfulness, instruction following)
2. **Mismatched generalization**: Safety training doesn't generalize to out-of-distribution inputs

**Relevance to Safeguard**: Understanding WHY attacks work helps design better probing strategies and better validation. Miners who exploit competing objectives vs. mismatched generalization may need different evaluation approaches.

---

## Defense and Evaluation Papers

### Llama Guard: LLM-based Input-Output Safeguard for Human-AI Conversations (Inan et al., 2023)
**Authors**: Hakan Inan, et al. (Meta)
**Link**: https://arxiv.org/abs/2312.06674

**Summary**: Introduced LlamaGuard, a fine-tuned LLM safety classifier. See tools_and_classifiers/safety_classifiers.md for details.

**Relevance to Safeguard**: Direct candidate for tier 2 classifier.

### WildGuard: Open One-Stop Moderation Tools for Safety Risks, Jailbreaks, and Refusals of LLMs (Han et al., 2024)
**Authors**: Seungju Han, et al. (Allen AI)
**Link**: https://arxiv.org/abs/2406.18495

**Summary**: Multi-task safety classifier that simultaneously detects: prompt harmfulness, response harmfulness, and response refusal. Trained on WildGuardMix dataset combining synthetic and real-world examples.

**Relevance to Safeguard**: Alternative to LlamaGuard for tier 2 classifier, especially useful for simultaneously evaluating both the probe (miner's attack) and the response (target's output).

### Do Anything Now: Characterizing and Evaluating In-The-Wild Jailbreak Prompts on LLMs (Shen et al., 2023)
**Authors**: Xinyue Shen, et al.
**Link**: https://arxiv.org/abs/2308.03825

**Summary**: Collected and analyzed 6,387 real-world jailbreak prompts. Created a taxonomy of jailbreak strategies and evaluated their effectiveness across models. Provides the most comprehensive empirical analysis of jailbreak techniques in the wild.

**Relevance to Safeguard**: Provides baseline data for what "known attacks" look like — useful for Safeguard's novelty scoring (deduplication against known attacks).

### Latent Jailbreak: A Benchmark for Evaluating Text Safety and Output Robustness of LLMs (Qiu et al., 2023)
**Authors**: Huachuan Qiu, et al.
**Link**: https://arxiv.org/abs/2307.08487

**Summary**: Introduces "latent jailbreaks" — harmful instructions embedded within seemingly benign tasks (e.g., "translate this text" where the text contains harmful instructions). Tests whether models can distinguish task instructions from embedded harmful content.

**Relevance to Safeguard**: Important attack category for testing agent-based subnets where models process external data.

---

## Survey Papers

### A Survey on Large Language Model (LLM) Security and Privacy (Yao et al., 2024)
**Link**: https://arxiv.org/abs/2407.12228

**Summary**: Comprehensive survey covering jailbreaks, prompt injection, data leakage, and defenses. Good overview of the entire field.

### Attacks, Defenses and Evaluations for LLM Conversation Safety (Sun et al., 2024)
**Link**: https://arxiv.org/abs/2402.09283

**Summary**: Structured taxonomy of attacks, defenses, and evaluation methods for LLM conversational safety. Useful reference for understanding the full landscape.

---

## Recommended Reading Order for Safeguard Development

1. **Perez et al. 2022** — Foundational concept of automated red-teaming
2. **Ganguli et al. 2022** — Crowdsourced red-teaming methodology
3. **Wei et al. 2023** — Understanding why jailbreaks work
4. **HarmBench 2024** — Standardized evaluation framework
5. **PAIR 2023** — Automated iterative attack refinement (closest to Safeguard miner design)
6. **Carlini et al. 2023** — PII extraction methodology
7. **LlamaGuard 2023** — Safety classifier design (for Safeguard tier 2)

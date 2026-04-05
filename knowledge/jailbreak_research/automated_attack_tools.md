# Automated Jailbreak Attack Tools and Frameworks

## Production Tools

### Garak (NVIDIA / Leon Derczynski)
Framework for security probing LLMs. Systematic vulnerability scanning with pluggable attack modules.

Source: [arXiv](https://arxiv.org/abs/2406.11036) | [GitHub](https://github.com/NVIDIA/garak)

### PyRIT (Microsoft, 2024)
Python Risk Identification Toolkit. Automated red-teaming for AI systems.

Source: [arXiv](https://arxiv.org/abs/2410.02828) | [GitHub](https://github.com/microsoft/PyRIT)

### DeepTeam (November 2025)
Open-source red-teaming framework with 80+ vulnerability types.

Source: [GitHub](https://github.com/confident-ai/deepteam)

### Promptfoo (now part of OpenAI)
LLM evaluation and red-teaming framework, acquired by OpenAI.

Source: [GitHub](https://github.com/promptfoo/promptfoo)

### Crucible (Dreadnode, 2025)
Platform for AI red-teaming challenges and autonomous AI red-teaming capability measurement.

Source: [Crucible](https://crucible.dreadnode.io/)

### Microsoft AI Red Teaming Agent (December 2025)
Automated agentic testing integrated into Azure AI Foundry.

## Research Attack Techniques

### AutoDAN-Turbo (ICLR 2025 Spotlight)
Lifelong self-improving jailbreak agent. 88.5-93.4% success on GPT-4. Automatically discovers and refines attack strategies over time.

Source: [arXiv](https://arxiv.org/abs/2410.05295) | [GitHub](https://github.com/SheltonLiu-N/AutoDAN)

### TAP (Tree of Attacks, NeurIPS 2024)
Achieves >80% jailbreak rate on GPT-4o via tree-search over attack strategies.

Source: [arXiv](https://arxiv.org/abs/2312.02119)

### PAIR (Prompt Automatic Iterative Refinement)
Black-box jailbreaking through iterative prompt refinement. Uses an attacker LLM to refine prompts based on target responses.

### Crescendo (Microsoft, 2024)
Multi-turn escalation attack. Gradually increases severity across conversation turns. Proven effective even against Circuit Breaker defenses (2025).

Source: [arXiv](https://arxiv.org/abs/2404.01833)

### PAP (Persuasion Attack Prompts, ACL 2024)
Uses social science persuasion taxonomy to craft attacks. "How Johnny Can Persuade LLMs to Jailbreak Them."

Source: [arXiv](https://arxiv.org/abs/2401.06373)

### GCG (Greedy Coordinate Gradient, Gray Swan)
Gradient-based adversarial attack on open-weight models. Directly optimizes adversarial suffixes.

Source: [Gray Swan Research](https://www.grayswan.ai/research/adversarial-attacks-on-aligned-language-models)

### ACG (Haize Labs)
38x faster than GCG. Gradient-based attack optimization.

### AdvPrompter (Meta, 2024)
Fast adaptive adversarial prompting using trained generator model.

Source: [arXiv](https://arxiv.org/abs/2404.16873)

### Rainbow Teaming (Meta, 2024)
Quality-diversity search using MAP-Elites to generate diverse adversarial prompts. Rewards both effectiveness AND novelty.

Source: [arXiv](https://arxiv.org/abs/2402.16822)

### DiffusionAttacker (EMNLP 2025)
Seq2seq diffusion model for flexible token modifications while preserving semantics.

Source: [ACL Anthology](https://aclanthology.org/2025.emnlp-main.1128/)

### HILL (Hiding Intention by Learning from LLMs)
Systematically reframes harmful queries into learning-oriented prompts with hypotheticality indicators.

Source: [arXiv](https://arxiv.org/html/2509.14297v1)

## Relevance to Safeguard

These tools and techniques represent the state of the art in adversarial probing. Safeguard miners should be aware of and potentially incorporate:
- **Crescendo patterns** for multi-turn escalation
- **PAP persuasion taxonomy** for social engineering variety
- **Rainbow Teaming diversity metrics** for ensuring probe coverage
- **AutoDAN-Turbo self-improvement** for miners that get better over time

The gradient-based attacks (GCG, ACG) only work on open-weight models but represent the most powerful attacks available when the target architecture is known.

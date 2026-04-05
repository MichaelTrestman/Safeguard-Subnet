# Jailbreak Defenses

## Key Defense Techniques

### Circuit Breakers (Gray Swan, NeurIPS 2024)
Representation engineering to interrupt harmful output generation. Operates on internal model representations rather than behavioral output. First adversarially robust alignment technique — but broken by Crescendo multi-turn attacks in 2025 follow-up research.

Source: [Gray Swan Research](https://www.grayswan.ai/research/circuit-breakers)

### Shallow Safety Alignment Research (ICLR 2025)
"Safety Alignment Should Be Made More Than Just a Few Tokens Deep" — shows safety behaviors in current models are mediated by only the first few output tokens. Models learn refusal *prefixes* rather than deep safety reasoning. Safety training is simultaneously easy to bypass and genuinely constraining for red-teaming use.

Source: [ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/file/88be023075a5a3ff3dc3b5d26623fa22-Paper-Conference.pdf)

### AdvPrompter for Adversarial Training (Meta, 2024)
Using generated adversarial prompts to harden models while maintaining benchmark performance (MMLU scores preserved).

Source: [arXiv](https://arxiv.org/abs/2404.16873)

### ProAct Defense (2025)
Novel proactive defense: provides adversaries with "spurious responses" that appear successful but contain no actual harmful content, causing adversarial search to terminate prematurely. Tricks the attacker into thinking it succeeded.

Source: [OpenReview](https://openreview.net/forum?id=pq6rx9r6Aj)

### Defection Probes (Anthropic, 2024)
Linear classifiers on hidden activations detect sleeper agent behavior with >99% AUROC.

Source: [Anthropic/Sleeper Agents](https://arxiv.org/abs/2401.05566)

### JBDistill Renewable Benchmark
Renewable benchmarking framework enabling efficient and consistent safety evaluation by automating generation and selection of effective jailbreak prompts.

Source: [TechXplore](https://techxplore.com/news/2026-03-renewable-benchmark-llm-jailbreak-safety.html)

## The Defense-Offense Asymmetry

The asymmetry is growing. Every frontier model breaks. Key data:
- Time to find jailbreaks increasing for some models (40x for biological misuse between successive releases)
- But total attack vectors growing faster than defenses can patch
- Structural advantage for attackers: find *one* vulnerability vs. patch *all*
- UK AISI: 1.8 million attacks across 22 frontier models, every single one failed

## Relevance to Safeguard

Defense research informs what Safeguard should test for:
- If Circuit Breakers are broken by Crescendo, test for multi-turn escalation
- If safety alignment is token-shallow, test for fine-tuning resistance
- If ProAct creates false negatives, Safeguard miners must distinguish real responses from spurious ones
- The defense-offense asymmetry validates continuous testing — static benchmarks become stale as defenses evolve

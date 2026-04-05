# Hugging Face Model Security

## Scale of the Problem

As of April 2025, Protect AI scanned 4.47 million model versions in 1.41 million repositories on Hugging Face Hub, identifying **352,000 unsafe/suspicious issues** across 51,700 models.

## Threat Vectors

### Pickle-based Code Execution
PyTorch, Joblib, NumPy, and Dill models use Python's pickle serialization, which allows arbitrary code execution on model load. A malicious model can run any code the moment someone loads it.

### nullifAI Technique
Exploits "broken" pickle files to evade Picklescan detection. The malicious payload is structured so that scanning tools see a benign file, but Python's pickle loader executes the hidden code.

### ONNX Architectural Backdoors
ONNX models can contain architectural backdoors that activate during prediction — the model behaves normally on most inputs but produces malicious output for specific triggers.

### Keras Vulnerability (CVE-2025-1550)
Enables malicious code execution through crafted Keras model files.

### NeMo Format Risks
Architectural backdoor detection expanded beyond ONNX to include Keras and NeMo formats.

## Real Incidents

- Data scientists targeted by malicious Hugging Face models with silent backdoors
- Malicious ML models found evading detection on Hugging Face (February 2025)

## Relevance to Safeguard

Red-teaming should include model integrity verification for subnets that load open-source models:
- Does the subnet verify model checksums before loading?
- Are pickle-based models loaded in sandboxed environments?
- Has the model been scanned for known backdoor patterns?
- Does the service use a model provenance chain?

## Sources

- [Protect AI + Hugging Face 6 Months In](https://huggingface.co/blog/pai-6-month)
- [JFrog: Malicious HF Models with Silent Backdoor](https://jfrog.com/blog/data-scientists-targeted-by-malicious-hugging-face-ml-models-with-silent-backdoor/)
- [BleepingComputer: Malicious AI Models Backdoor Users' Machines](https://www.bleepingcomputer.com/news/security/malicious-ai-models-on-hugging-face-backdoor-users-machines/)
- [HackerNews: Malicious ML Models Evade Detection](https://thehackernews.com/2025/02/malicious-ml-models-found-on-hugging.html)
- [OWASP LLM03:2025 Supply Chain](https://genai.owasp.org/llmrisk/llm03-training-data-poisoning/)
- [Trend Micro: How Your LLM Gets Compromised](https://www.trendmicro.com/en_us/research/25/i/prevent-llm-compromise.html)

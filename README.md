# 🏆 Graph-Guided Declarative Sub-Agents for Autonomous Software Engineering on Quantized Gemma 4 (`W4A16`)

![Gemma 4 Developer Agent Cover](assets/gemma4_swe_paper_cover.jpg)

> **Official Submission & Research Paper Repository — Google: The Gemma 4 Developer Agent Competition & Paper Track**  
> **Author:** **Robina Mirbahar — Google Cloud & AI Architect** (`@robinamirbahar`)  
> **License:** **Apache License 2.0** (OSI-Approved, Commercial-Friendly Open Source License)

> **Author & Architect:** [Robina Mirbahar](https://github.com/RobinaMirbahar) ([Google Developer Expert in Cloud & AI](https://developers.google.com/profile/u/106918534005910641104?utm_campaign=deveco_gdemembers&utm_source=deveco) · Google Cloud Champion Innovator · Co-Author of [*AI Engineering*](https://www.amazon.com/dp/B0GWCZWCF4))  
> 📚 **Competition & Paper Track:** Google — The Gemma 4 Developer Agent Competition & Paper Track (SWE-Gemma Benchmark)  
> **Core Stack:** Quantized [Google Gemma 4](https://ai.google.dev/gemma/docs?utm_campaign=deveco_gdemembers&utm_source=deveco) (gemma-4-12b-it-qat-w4a16-ct), Declarative Sub-Agents (gent.yaml / code_analyzer.yaml), 2-Hop Structural Code-Graph Tools (swegemma.graph), and vLLM.

---
## 📄 Abstract

Autonomous software engineering (SWE) agents operating on local, quantized open-weights models face a fundamental tension between **repository exploration depth** and **context-window/wall-clock compute budgets**. In the **SWE-Gemma** benchmark environment—where agents must resolve real-world Python issues across large repositories (`fastapi`, `httpx`, `rich`, `pydantic`, `requests`) within a strict **12-hour offline runtime budget**—monolithic agents using `gemma-4-31b-it-qat-w4a16-ct` with unconstrained `<|think|>` reasoning tokens and bash `grep` loops suffer from severe context pollution (`>28,000` tokens/task) and a `24.0%` task timeout rate.

In this work, we introduce a **Graph-Guided Declarative Sub-Agent Architecture** compiled natively via `swegemma`'s declarative `agent.yaml` security model on **`gemma-4-12b-it-qat-w4a16-ct`**. By decoupling **2-Hop Structural Code-Graph Localization** (`search_similar_code` $\rightarrow$ `get_code_neighbors` $\rightarrow$ `get_code_subgraph`) into a low-temperature specialist sub-agent (`sub_agents/code_analyzer.yaml`) and reserving high-budget reasoning for minimal patch synthesis and `pytest` verification in the root `LlmAgent`, our approach reduces average context token consumption by **68.5%** (`28,450` $\rightarrow$ `8,960` tokens), eliminates 12-hour harness timeouts (`0.0%`), and improves issue resolution from **32.0% to 54.0%** (+22.0 percentage points).

---

## 🏗️ 4-Stage Declarative Architecture

![Graph-Guided Declarative Sub-Agent Architecture](assets/gemma4_swe_graph_arch.jpg)

### 📐 Color-Coded Graph-Guided Declarative Sub-Agent Flow
> *(🩷 Pink = SWE-Gemma Issue & Declarative YAML | 💙 Blue = Low-Temp 2-Hop Code-Graph Sub-Agent | 💚 Green = Root LlmAgent Patch Synthesis | 💜 Purple = Sandboxed Pytest Verification & 54.0% Resolution)*

```mermaid
flowchart TD
    subgraph Input ["1. SWE-Gemma Task & Declarative Manifest (agent.yaml)"]
        T_Issue["Repository Issue Description (fastapi / httpx / pydantic)"]
    end
    subgraph GraphAgent ["2. Specialist Sub-Agent (sub_agents/code_analyzer.yaml)"]
        G_Hop1["search_similar_code -> get_code_neighbors (2-Hop Graph)"]
        G_Hop2["get_code_subgraph (68.5% Context Reduction: 8,960 Tokens)"]
    end
    subgraph RootAgent ["3. Root LlmAgent (gemma-4-12b-it-qat-w4a16-ct)"]
        R_Patch["Adaptive Thinking Budget & Minimal Diff Synthesis"]
    end
    subgraph Verify ["4. Deterministic Test Verification"]
        V_Test["Isolated pytest Execution & Regression Check (0.0% Timeout)"]
    end
    T_Issue --> G_Hop1 --> G_Hop2 --> R_Patch --> V_Test

    style T_Issue fill:#fce7f3,stroke:#db2777,stroke-width:2px,color:#831843
    style G_Hop1 fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#1e3a8a
    style G_Hop2 fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#1e3a8a
    style R_Patch fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#14532d
    style V_Test fill:#f3e8ff,stroke:#9333ea,stroke-width:2px,color:#581c87
```


### Why Baseline Submissions Fail (`compile_submission` & Runtime Pitfalls)
1. **Single Base Model Violation:** The `swegemma` submission compiler strictly prohibits mixing different base models across `agent.yaml` and `sub_agents/*.yaml`. Our build pipeline programmatically synchronizes `model: gemma-4-12b-it-qat-w4a16-ct` across all manifests.
2. **Archive Root Nesting Violation:** `agent.yaml` must sit directly at the root of `submission.zip` (not inside a nested `submission/` folder).
3. **Declarative-Only Security Model:** Arbitrary `.py` scripts inside `submission.zip` are rejected; all orchestration is declared via `LlmAgent` YAML manifests, `!include` directives, and the closed host `ToolRegistry`.

---

## 📊 Experimental Ablation Results

| Configuration ID | Base Model (`QAT W4A16`) | Architecture & Exploration Strategy | Resolved (%) | Avg Context Tokens | Turns to Localize | Timeout Rate (%) | 50-Task Wall Clock (h) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **`C1_Baseline_31B`** | `gemma-4-31b-it-qat-w4a16-ct` | Monolithic Agent (`bash grep` + unconstrained `<\|think\|>`) | `32.0%` | `28,450` | `9.4` | `24.0%` | `14.8 h` *(Exceeds 12h)* |
| **`C2_Baseline_12B`** | `gemma-4-12b-it-qat-w4a16-ct` | Monolithic Agent (`bash grep` + standard prompt) | `36.0%` | `24,120` | `8.6` | `6.0%` | `6.2 h` |
| **`C3_Graph_12B`** | `gemma-4-12b-it-qat-w4a16-ct` | Single Agent + 2-Hop `swegemma.graph` Tools | `48.0%` | `9,840` | `2.8` | `2.0%` | `4.1 h` |
| **`C4_Ours_SubAgent_12B`** | `gemma-4-12b-it-qat-w4a16-ct` | **Root `LlmAgent` + `code_analyzer` Sub-Agent + Adaptive Budget** | **`54.0%`** | **`8,960`** | **`2.3`** | **`0.0%`** | **`3.7 h`** |

---

## 📦 Repository Contents & Reproducibility

```text
gemma4-swe-graph-agent/
├── submission.zip                                 # Ready-to-upload Kaggle submission archive
├── submission/                                    # Source declarative manifests
│   ├── agent.yaml                                 # Root LlmAgent coordinator
│   ├── eval_config.yaml                           # Per-task execution & tool budgets
│   ├── configs/
│   │   └── sampling.yaml                          # Root generation parameters
│   ├── prompts/
│   │   ├── system.md                              # 4-Stage SWE execution protocol
│   │   └── analyzer.md                            # 2-Hop Code-Graph localization prompt
│   └── sub_agents/
│       └── code_analyzer.yaml                     # Graph-first localization specialist
├── notebooks/
│   └── gemma4_developer_agent_robina.ipynb        # Step-by-step zero-error Kaggle Notebook
├── scripts/
│   └── build_and_verify_submission.py             # Compiler validator & zip builder
├── KAGGLE_WRITEUP.md                              # Full Paper Track Writeup
└── LICENSE                                        # Apache-2.0 (OSI-Approved)
```

### Build & Validate `submission.zip` Locally or in Cloud Shell / Kaggle
```bash
python scripts/build_and_verify_submission.py
```
---

### Official Google Developer Resources
- [Google Gemma Open Models Documentation](https://ai.google.dev/gemma?utm_campaign=deveco_gdemembers&utm_source=deveco)
- [Google Agent Development Kit (ADK) Docs](https://google.github.io/adk-docs/?utm_campaign=deveco_gdemembers&utm_source=deveco)

# AURORA: Agentic Survey Generation with Rubric-Guided Self-Improvement

AURORA is a modular, multi-agent framework for automated academic survey generation and iterative refinement. It integrates citation-aware writing agents with a rubric-based evaluation loop (Agentic Reinforcement Learning, or ARL) to produce high-quality, self-improving scientific papers.

## 🌐 Project Highlights

- **Agentic Writing System**: Decomposes survey writing into agent-driven phases for retrieval,  drafting, editing, and refinement.
- **Rubric-as-Reward (RaR)**: Uses structured reviewer feedback (from GPT-4.1, Gemini 2.5, Claude 3.7) to guide stepwise improvements.
- **Zero-Retrain Self-Improvement**: Refinement is driven purely by reviewer critique—no policy learning or retraining needed.
- **PDF Comparison Suite**: Multiple output rounds show how ARL improves draft quality in stages.

## 📁 Folder Structure

```text
.
├── agent_prompt.py                    # All prompt definitions used by AURORA agents
├── citation/                          # Source citations extracted or curated
├── partial_outlines/                 # Intermediate outline results
├── references/                       # Final BibTeX references
├── survey_paper.tex                  # LaTeX survey document Before ARL 
├── review_output/                    # Excel logs and feedback per round (scores, suggestions)
├── pdf_output/                       # Compiled PDFs per refinement round (Last round is the Final PDF/LaTex. e.g., final_paper_round3.pdf, ...)
├── topics/                           # Research area list (aligned with human-written survey comparisons)
├── [research area folders]/          # One folder per survey topic (e.g., LLM reasoning, synthetic data, etc.)
│   └── Contains citations, papers, and outputs per area
│`full_detailed_review_rubric.json`  #The complete structured rubric used for reviewer simulation, broken down into 7 categories and 20+ sub-criteria. This rubric powers the Agentic Reinforcement Learning (ARL) loop by producing standardized, interpretable feedback that drives self-improvement.


 
---

### `partial_outlines/`
- Markdown outline snippets used for paper construction (intermediate agent outputs)

---

### `review_output/`
- `round{n}_section_feedback.xlsx`: Section-level reviewer suggestions from agents
- `round{n}_category_scores.xlsx`: Rubric scores across categories (e.g., originality, clarity)
- `round{n}_overall_evaluation.xlsx`: Overall judgment from each agent reviewer
- `score_summary.xlsx`: Consolidated score tracker per round
- `total_score.txt`: Final cumulative score (target ≥ 90%)

---

### `pdf_output/`
- `final_paper_round{n}.pdf`: Compiled paper version per refinement round
- Includes logs (`.aux`, `.bbl`, `.out`, `.log`) and raw LaTeX files per version

---

 

---

 

---
 


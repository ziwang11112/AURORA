# AURORA:An Agentic Writing System Leveraging Rubric-Guided Reinforcement Learning

AURORA is a modular, multi-agent framework for automated academic survey generation and iterative refinement. It integrates citation-aware writing agents with a rubric-based evaluation loop (Agentic Reinforcement Learning, or ARL) to produce high-quality, self-improving scientific papers.

## 🌐 Project Highlights

- **Agentic Writing System**: Decomposes survey writing into agent-driven phases for retrieval,  drafting, editing, and refinement.
- **Rubric-as-Reward (RaR)**: Uses structured reviewer feedback (from GPT-4.1, Gemini 2.5, Claude 3.7) to guide stepwise improvements.
- **Zero-Retrain Self-Improvement**: Refinement is driven purely by reviewer critique—no policy learning or retraining needed.
- **PDF Comparison Suite**: Multiple output rounds show how ARL improves draft quality in stages.

## 📁 Folder Structure

```text
.
├── AURORA_Source_Code/                 # Full pipeline, experiment, and evaluation source code and scripts. 
├── agent_prompt                        # All prompt definitions used by AURORA agents
├── full_detailed_review_rubric         # The complete rubric (7 categories, 20+ sub-criteria)
├── SMALL_model_sample_by4.1mini/       # Sample surveys and outputs generated by the small (GPT-4.1 mini) model
├── AURORA_sample_surveys_ouput_gpt4.1/ # Sample surveys and outputs generated by GPT-4.1 (main model)
├── experiment/                         # All experiment results, including comparison tables and figures
├── human_evaluation/                   # Results and tables from blinded human expert evaluation
├── Dataset/                            # Baseline and comparison papers, review results for all systems
│   ├── autosurvey/                         # Outputs from the Autosurvey baseline
│   ├── dataset_review_result/
│   │   ├── review_autosurvey/               # Review logs and chunked review for Autosurvey
│   │   ├── review_published/                # Review logs for human-written published surveys
│   │   ├── review_surveyforge/              # Review logs for SurveyForge
│   │   └── review_surveyx/                  # Review logs for SurveyX
│   ├── published/                           # Human-written (published) survey papers (PDF or LaTeX)
│   ├── surveyforge/                         # Outputs from SurveyForge baseline
│   └── surveyx/                             # Outputs from SurveyX baseline
├── README                                  # This file
└── .gitignore
```
### 📑 Folder Details
**AURORA_sample_surveys_ouput_gpt4.1/**
All sample surveys and outputs generated using GPT-4.1 as the writing model. For each survey topic (e.g., "Disease detection across modalities"), you will find:

– **partial_outlines.md**
Markdown outline snippets used by agents during intermediate survey drafting.

– **completed_research_paper.md and completed_research_paper.tex**
Final, post-refinement survey draft in both Markdown and LaTeX formats.

– **survey_paper.tex / survey_paper_outline_one_by_one.md**
Initial and intermediate versions of the survey draft and outline.

– **citation.csv, summaries_dedup.csv, references.bib, topics.csv**
All source citations, deduplicated summary data, BibTeX references, and topic lists for the survey.

– **review_output/**
Automated review logs and scores for every refinement round:

round{n}_section_feedback.csv: Section-by-section feedback from reviewer agents.

round{n}_category_scores.csv: Rubric-aligned category scores (e.g., originality, clarity, coverage).

round{n}_overall_evaluation.csv: Overall evaluation and high-level judgment from each reviewer agent.

score_summary.csv: Tracker of overall score progression across rounds.

total_score.txt: Final cumulative score for the paper (target ≥ 90%).

– **pdf_output/**
Compiled PDFs and logs for every round of refinement:

final_paper_round{n}.pdf: Compiled survey PDF for each ARL refinement round (e.g., round0 is initial, roundN is final).

final_paper_round{n}.tex: Raw LaTeX file for each round.

.aux, .bbl, .blg, .out, .log: Auxiliary files from LaTeX build for transparency and full reproducibility.

**SMALL_model_sample_by4.1mini/**
All surveys and outputs generated by running the full system pipeline using GPT-4.1 mini as the agent. Useful for demonstrating robustness to smaller models.

**experiment/**
Contains all comparison results, ablation experiment data, and generated figures referenced in the paper and supplement.

**Dataset/**
Includes all baseline and comparison papers:

Human-written published surveys

Papers generated by baseline systems (e.g., Autosurvey, SurveyForge, SurveyX)

Subfolders contain review results and reviewer logs for each baseline.

### 🔬 Evaluation & Reproducibility
Human Evaluation:
See human_evaluation/ for blinded expert reviewer results (4 reviewers, 5 topics, before/after RL refinement).

Ablation Studies:
See SMALL_model_sample_by4.1mini/ and corresponding tables/plots in experiment/ for robustness with smaller models.

Baseline Reviews:
All datasets and reviews for human and automated baselines are organized under Dataset/.

experiment_result.py:
Full experimental results, reviewer scores, and system outputs are available in this repository to support transparency and reproducibility.


## Source code
## Environment Setup
### 1. Install Python Requirements
```sh
pip install -r requirements.txt
```

### 2. Install LaTeX
You must have a working LaTeX toolchain (pdflatex, bibtex).

```sh
sudo apt install texlive-full
```
## Configuration
Updated the API_KEY for LLMS in .env file with the following content:

SERPER_API_KEY=YOUR_SERPER_API_KEY
PAPER_COUNT=15                # Number of papers per topic
JOURNAL=acm                   # Target journal
OPENAI_API_KEY=YOUR_OPENAI_API_KEY
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
MODEL=gpt-4.1                 # (e.g., gpt-4.1, gpt-4.1-mini, gemini-1.5-pro, etc.)
TEMPERATURE=0.7
TOPIC=                        # Topic will be set in the first script or batch run
ANTHROPIC_API_KEY=YOUR_ANTHROPIC_API_KEY

## Usage

### One-click: Full Pipeline
Run everything from scratch:

```sh
python run_all.py

```
### Phase-by-phase
You can also run each phase individually depending on your needs (e.g., search, summarization, LaTeX build, BibTeX conversion, etc.).
See the individual scripts in AURORA_Source_Code/ for details and configuration options.
### Notes
First Stage (0userinput.py):
Requires human input for topic selection, ensuring only approved topics proceed through the pipeline.

**CrewAI Environment**:
Make sure all CrewAI and LLM provider packages are installed and correctly configured.

**Script Flexibility**:
All scripts can be run independently for debugging, custom runs, or partial pipeline execution.

**Custom Topics & Models**:
To switch topics, model backends, or paper counts, update the .env file as needed.

**Questions or issues?** Please see the README or open an issue in this repository.



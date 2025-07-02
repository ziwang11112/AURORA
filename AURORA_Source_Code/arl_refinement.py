import os
import re
import json
import shutil
import subprocess
import pandas as pd
import glob

import warnings
from dotenv import load_dotenv
from crewai import Agent, Crew, Process, Task, LLM
from PyPDF2 import PdfReader
from crewai.tools import BaseTool
from tqdm import tqdm 
warnings.filterwarnings('ignore')

#export PATH="/home/zwang/texlive/2025/bin/x86_64-linux:/usr/bin:/bin"

# === Load Environment
load_dotenv()
os.environ["MODEL"] = "gpt-4.1-mini"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
print("✅ Loaded API keys")

# === Clean previous outputs
for folder in ["review_output", "pdf_output", "output"]:
    if os.path.exists(folder):
        shutil.rmtree(folder)
    os.makedirs(folder, exist_ok=True)

# === Initialize LLMs
llm_gpt     = LLM(model="gpt-4.1", temperature=0)
llm_gemini  = LLM(model="gemini/gemini-2.5-pro-preview-03-25", temperature=0)
llm_claude = LLM(
    model="claude-3-7-sonnet-20250219",  # or "claude-3-7-sonnet-20250219" depending on your provider
    temperature=0
)
llm_final = LLM(model="gpt-4.1", temperature=0)

# === Define PDF Reader Tool
# === PDF Reader Tool
class PDFReadertool(BaseTool):
    name: str = "pdf_reader"
    description: str = "Read a local PDF file."

    def _run(self, pdf_path: str, page_limit: int = 1000):
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages[:page_limit]:
            page_text = page.extract_text() or ""
            text += page_text + "\n\n"
        return text


pdf_reader_tool = PDFReadertool()


# === Monkey-patch Crew
from crewai import Crew
original_kickoff = Crew.kickoff
def safe_kickoff(self, *args, **kwargs):
    result = original_kickoff(self, *args, **kwargs)
    return getattr(result, "output", str(result))
Crew.kickoff = safe_kickoff

# === Define Reviewer Agents
reviewer_agent_gpt = Agent(
    role="Survey Reviewer GPT-4",
    goal="Review academic survey using rubric.",
    backstory="An experienced academic peer reviewer specializing in evaluating AI survey papers.",
    verbose=True,
    model=llm_gpt,
    tools=[pdf_reader_tool],
    allow_delegation=False,
    memory=False
)

reviewer_agent_gemini = Agent(
    role="Survey Reviewer Gemini",
    goal="Review academic survey using rubric.",
    backstory="An experienced academic peer reviewer specializing in evaluating AI survey papers.",
     verbose=True,
    model=llm_gemini,
    tools=[pdf_reader_tool],
    allow_delegation=False,
    memory=False
)
reviewer_agent_claude = Agent(
    role="Survey Reviewer Claude",
    goal="Review academic survey using rubric.",
    backstory="An experienced academic peer reviewer specializing in evaluating AI survey papers.",
    verbose=True,
    model=llm_claude,
    tools=[pdf_reader_tool],
    allow_delegation=False,
    memory=False
)
# === Define Review Task
# Load detailed rubric
def load_rubric():
    with open("full_detailed_review_rubric.json") as f:
        return json.load(f)

# Turn rubric JSON into a readable string
def generate_rubric_prompt_blocks(rubric_dict):
    lines = []
    for category, submap in rubric_dict.items():
        lines.append(f"=== {category.upper()} ===")
        for subcrit, scores in submap.items():
            lines.append(f"  Sub-Criterion: {subcrit}")
            for score in sorted(scores.keys(), key=int, reverse=True):
                lines.append(f"    {score}: {scores[score]}")
            lines.append("")  # Empty line for readability
    return "\n".join(lines)

# Chunk a PDF into labeled sections
def chunk_pdf_by_n_pages(pdf_path, n=3, max_pages=100):
    from PyPDF2 import PdfReader
    reader = PdfReader(pdf_path)
    chunks = []
    total_pages = min(len(reader.pages), max_pages)
    for i in range(0, total_pages, n):
        text = ""
        for j in range(i, min(i + n, total_pages)):
            page_text = reader.pages[j].extract_text() or ""
            text += page_text + "\n\n"
        label = f"Pages {i+1}–{min(i+n, total_pages)}"
        chunks.append((label, text.strip(), i))
    return chunks

def review_chunk_task(chunk_text: str, chunk_label: str, rubric_text: str) -> Task:
    return Task(
        description=(
            f"You are reviewing a section of an academic survey paper labeled: {chunk_label}.\n\n"
            f"=== SECTION START ===\n{chunk_text}\n=== SECTION END ===\n\n"
            "Use the rubric below strictly. Score each sub-criterion from 1 to 5. Do not skip any. Do not add new criteria.\n\n"
            f"{rubric_text}\n\n"
            "Return a JSON object with the following structure:\n"
            "{\n"
            '  "scores": [\n'
            '    {\n'
            '      "category": "CategoryName",\n'
            '      "comment": "General comment for this category (required if any sub-score is < 5)",\n'
            '      "Sub-Criterion-A": 4,\n'
            '      "Sub-Criterion-B": 5,\n'
            '      ...\n'
            '    },\n'
            '    ...\n'
            '  ],\n'
            '  "section_feedback": [\n'
            '    {\n'
            '      "section": "<Please identify and write the section title shown in this chunk>",\n'
            '      "Strengths": [...],\n'
            '      "Weaknesses": [...],\n'
            '      "Suggestions": [...]\n'
            '    }\n'
            '  ],\n'
            '  "overall_evaluation": {\n'
            '    "summary": "...",\n'
            '    "major_strengths": [...],\n'
            '    "major_weaknesses": [...],\n'
            '    "recommendations": [...],\n'
            '    "final_score": number,\n'
            '    "recommendation": "accept | minor revision | major revision | reject"\n'
            '  }\n'
            "}\n\n"
            "Important Instructions:\n"
            "- In the `section` field, use your best judgment to name the section or subsection from the text (e.g., 'Introduction', '2.3 Methods', '3.2.1 Survey Automation')\n"
            "- For every sub-criterion scored less than 5, briefly explain the reasoning in the `comment` field.\n"
            "- Do NOT invent new sub-criteria.\n"
            "- Return ONLY valid raw JSON. No markdown, no quotes, no explanations outside the JSON block."
        ),
        expected_output="Rubric-based JSON review for this chunk.",
        agent=None,
        model=None,
        human_input=False
    )


# === Full Rubric-Based Chunked Review
def review_paper_by_chunks(pdf_path):
    rubric = load_rubric()
    rubric_text = generate_rubric_prompt_blocks(rubric)
    chunks = chunk_pdf_by_n_pages(pdf_path, n=3)

    all_category_rows = []
    all_section_rows = []
    all_overall_rows = []

    agents = [
        (reviewer_agent_gpt, "gpt-4.1"),
        (reviewer_agent_gemini, "gemini-2.5"),
        (reviewer_agent_claude, "claude-3.7")
    ]

    for chunk_label, chunk_text, chunk_idx in tqdm(chunks, desc="🔍 Reviewing Chunks"):
        for agent, name in agents:
            print(f"🧠 {name} reviewing {chunk_label}...")
            task = review_chunk_task(chunk_text, chunk_label, rubric_text)
            task.agent = agent
            crew = Crew(agents=[agent], tasks=[task], process=Process.sequential)
            result = crew.kickoff()

            if not result or result.strip() == "":
                print(f"⚠️ No output received from {name} for {chunk_label}.")
                continue

            try:
                parsed = json.loads(result)

                # === Parse scores ===
                for category_block in parsed.get("scores", []):
                    category = category_block.get("category", "").strip().title()
                    comment = category_block.get("comment", "")

                    if category not in rubric:
                        print(f"⚠️ Invalid category '{category}' in {name} on {chunk_label}")
                        continue

                    valid_subs = rubric[category].keys()
                    for subcrit, value in category_block.items():
                        if subcrit in ["category", "comment"]:
                            continue
                        if subcrit not in valid_subs:
                            print(f"⚠️ Invalid sub-criterion '{subcrit}' in {category} for {name} on {chunk_label}")
                            continue

                        all_category_rows.append({
                            "Model": name,
                            "Chunk": chunk_label,
                            "ChunkIndex": chunk_idx,
                            "Category": category,
                            "Sub-Criterion": subcrit,
                            "Score (1–5)": value,
                            "Comment": comment
                        })

                # === Parse section feedback ===
                for section in parsed.get("section_feedback", []):
                    all_section_rows.append({
                        "Model": name,
                        "Chunk": chunk_label,
                        "Section": section.get("section", ""),
                        "Strengths": "; ".join(section.get("Strengths", [])),
                        "Weaknesses": "; ".join(section.get("Weaknesses", [])),
                        "Suggestions": "; ".join(section.get("Suggestions", []))
                    })

                # === Parse overall evaluation ===
                if "overall_evaluation" in parsed:
                    overall = parsed["overall_evaluation"]
                    all_overall_rows.append({
                        "Model": name,
                        "Chunk": chunk_label,
                        "Summary": overall.get("summary", ""),
                        "Major Strengths": "; ".join(overall.get("major_strengths", [])),
                        "Major Weaknesses": "; ".join(overall.get("major_weaknesses", [])),
                        "Recommendations": "; ".join(overall.get("recommendations", [])),
                        "Final Score": overall.get("final_score", ""),
                        "Recommendation": overall.get("recommendation", "")
                    })

            except Exception as e:
                print(f"⚠️ Error parsing output from {name} on {chunk_label}: {e}")

    if not all_category_rows:
        print("⚠️ No valid scores extracted from any chunk.")
        return None

    return {
        "category_scores": all_category_rows,
        "section_feedback": all_section_rows,
        "overall_evaluation": all_overall_rows
    }







# === Define LaTeX Improvement Agent
improvement_agent = Agent(
    role="Survey Paper Improver",
    goal="Improve survey paper based on reviewer feedback, fixing weaknesses while preserving strengths.",
    verbose=True,
    model=llm_gpt,
    tools=[],
    backstory=(
        "You are an expert academic writing assistant specializing in improving AI survey papers. "
        "You read detailed reviewer feedback, locate weak areas, and revise the LaTeX document section-by-section, "
        "enhancing clarity, depth, originality, structure, and presentation without changing scientific contributions."
    ),
    allow_delegation=False,
    memory=False
)
 

def load_citation_summaries_by_refkey(csv_path="summaries_dedup.csv") -> dict:
    df = pd.read_csv(csv_path, index_col=0)
    ref_map = {}

    for idx, row in df.iterrows():
        ref_key = f"ref{int(idx)}"  # index 1 → ref1
        citation = row.get("Citation", "").strip()
        summary = row.get("Summary", "").strip()
        if summary:
            ref_map[ref_key] = f"{citation}\nSummary: {summary}"

    return ref_map
import re

def get_used_citations(text: str) -> list:
    raw_keys = re.findall(r'\\cite\{(.*?)\}', text)
    return sorted(set(k.strip() for entry in raw_keys for k in entry.split(',')))

def extract_relevant_summaries(text: str, citation_summary_dict: dict) -> str:
    used_keys = get_used_citations(text)
    return "\n\n".join([
        f"{key}:\n{citation_summary_dict[key]}"
        for key in used_keys if key in citation_summary_dict
    ])

def improve_paper_task(paper_content: str, low_scoring_feedback: str, citation_summaries: str) -> Task:
    if not paper_content.strip():
        return Task(
            description=(
                "The provided LaTeX content is empty and only contains a section or subsection heading.\n"
                "Do not add any content or explanation below it. Just return the heading exactly as given.\n"
                "Do not invent, summarize, or expand anything. Leave it as-is."
            ),
            expected_output=paper_content,
            agent=improvement_agent,
            model=llm_gpt,
            human_input=False
        )

    return Task(
        description=(
            "You are given a LaTeX section (one or more subsections) from an academic paper, along with structured reviewer feedback and citation summaries.\n\n"
            "Only revise the LaTeX if the section or subsection is explicitly mentioned in the feedback as needing improvement.\n"
            "Focus exclusively on addressing points listed in the **Suggestions** field of the feedback. Do not act on generic observations or strengths.\n"
            "If the Suggestions include adding diagrams or figures, **ignore those parts** — do not generate or insert any images or figures.\n"
            "You may insert or revise **tables** if explicitly suggested, but they must strictly follow the required LaTeX format.\n"
            "If no valid suggestion applies to the section, return the original LaTeX unchanged.\n\n"
            f"--- SECTION LATEX START ---\n{paper_content}\n--- SECTION LATEX END ---\n\n"
            f"--- LOW SCORING FEEDBACK START ---\n{low_scoring_feedback}\n--- LOW SCORING FEEDBACK END ---\n\n"
            f"--- CITATION SUMMARIES START ---\n{citation_summaries}\n--- CITATION SUMMARIES END ---\n\n"
            "Instructions:\n"
            "- Only revise sections or subsections explicitly targeted by reviewer Suggestions.\n"
            "- Never invent or introduce new citations or content not in the citation summaries.\n"
            "- Use citation summaries only to support reworded or clarified arguments.\n"
            "- Preserve original `~\\cite{}` syntax and citation style.\n"
            "- Do NOT use any LaTeX bullet environments such as `\\item`, `\\begin{itemize}`, or `\\begin{enumerate}`.\n"
            "- Do NOT insert or modify any figures, diagrams, or illustrations.\n"
            "- For tables, if required, follow this mandatory format:\n"
            "    \\begin{table*}[htbp]\n"
            "    \\centering\n"
            "    \\caption{<insert caption text>}\n"
            "    \\label{<insert label>}\n"
            "    \\begin{adjustbox}{max width=\\textwidth}\n"
            "    \\begin{tabular}{@{}llll@{}}\n"
            "    \\toprule\n"
            "    ... table content ...\n"
            "    \\bottomrule\n"
            "    \\end{tabular}\n"
            "    \\end{adjustbox}\n"
            "    \\end{table*}\n"
            "- Always return valid LaTeX. No commentary, explanations, or metadata.\n"
            "- Never reinterpret or modify scientific contributions or meaning.\n\n"
            "**Important**: Output only the fully improved (or unchanged) LaTeX section. Do NOT include any extra notes."
        ),
        expected_output="Improved LaTeX section that addresses reviewer suggestions and follows formatting rules.",
        agent=improvement_agent,
        model=llm_gpt,
        human_input=False
    )





def extract_low_scores_for_section(df_scores, section_label, model="gpt-4.1", threshold=4):
    # You likely meant to match against "Chunk" or "ChunkIndex", not "Section"
    filtered = df_scores[
        (df_scores["Model"] == model) &
        (df_scores["Score (1–5)"] < threshold) &
        (df_scores["Chunk"] == section_label)  # or use a more robust mapping
    ]
    return filtered.to_dict(orient="records")

# --- LaTeX Helpers ---
import re
import os

def extract_latex_title(text: str) -> str:
    idx = text.find(r'\title')
    if idx == -1:
        return ""
    brace_start = text.find('{', idx)
    if brace_start == -1:
        return ""
    count = 1
    i = brace_start + 1
    while i < len(text) and count > 0:
        if text[i] == '{':
            count += 1
        elif text[i] == '}':
            count -= 1
        i += 1
    content = text[brace_start+1 : i-1].strip()
    if content.startswith(r'\title'):
        return extract_latex_title(content)
    return content

def extract_abstract(text: str) -> str:
    m = re.search(r'\\begin\{abstract\}(.+?)\\end\{abstract\}', text, re.DOTALL)
    if not m:
        return ""
    body = m.group(1).strip()
    return f"\\begin{{abstract}}\n{body}\n\\end{{abstract}}"

def remove_original_preamble(text: str) -> str:
    text = re.sub(r'(?s)\\title\{.*?\}\s*\\maketitle', '', text)
    text = re.sub(r'(?s)\\begin\{abstract\}.*?\\end\{abstract\}', '', text)
    text = re.sub(r'(?m)^\s*\\(?:documentclass|usepackage|author|date|maketitle).*\n', '', text)
    text = re.sub(r'\\(?:begin|end)\{document\}', '', text)
    return text.strip()

def normalize_title(title: str) -> str:
    cleaned = re.sub(r'[#*]', '', title)
    cleaned = re.sub(r'\bsection\b', '', cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace(":", "")
    match = re.match(r'\s*([\d]+(?:\.[\d]+)*)', cleaned)
    return match.group(1).strip() if match else title.strip()

def split_latex_by_sections(text: str):
    pattern = re.compile(r'\\(section|subsection|subsubsection)\*?\{(.+?)\}', re.MULTILINE)
    matches = list(pattern.finditer(text))
    sections = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i+1].start() if i+1 < len(matches) else len(text)
        sections.append({
            "type": m.group(1),
            "title": m.group(2),
            "normalized_title": normalize_title(m.group(2)),
            "content": text[start:end].strip()
        })
    return sections

# --- Improve and Save ---
def improve_latex_file(tex_path: str, round_num: int, citation_summary_dict: dict):
    import pandas as pd
    from tqdm import tqdm

    with open(tex_path, "r", encoding="utf-8") as f:
        content = f.read()

    title = extract_latex_title(content)
    abstract = extract_abstract(content)
    body = remove_original_preamble(content)
    sections = split_latex_by_sections(body)

    # ✅ Load section-level feedback from CSV
    section_feedback_df = pd.read_csv(f"review_output/round{round_num}_section_feedback.csv")

    # === Improve all sections using section-specific suggestions
    improved_sections = []
    for sec in tqdm(sections, desc="🪠 Improving Sections", unit="section"):
        section_text = sec["content"]
        section_title = sec["normalized_title"]

        # Extract citation summaries used in this section
        citation_summaries = extract_relevant_summaries(section_text, citation_summary_dict)

        # Match feedback rows that mention this section (fuzzy match is OK)
        relevant_feedback_rows = section_feedback_df[
            section_feedback_df["Section"].str.contains(section_title, case=False, na=False)
        ]

        if relevant_feedback_rows.empty:
            low_scoring_feedback = ""
        else:
            # Join all suggestions (from all reviewers for this section)
            suggestions = relevant_feedback_rows["Suggestions"].dropna().tolist()
            low_scoring_feedback = "\n".join(suggestions)

        # Build task and run
        task = improve_paper_task(section_text, low_scoring_feedback, citation_summaries)
        crew = Crew(agents=[improvement_agent], tasks=[task], process=Process.sequential)
        improved = crew.kickoff()
        improved_sections.append(improved)

    # === Assemble full paper
    full_paper = f"\\title{{{title}}}\n\\maketitle\n\n{abstract}\n\n" + "\n\n".join(improved_sections)
    output_path = f"output/final_round{round_num}_paper.tex"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_paper)

    print(f"✅ Saved improved LaTeX to {output_path}")



def build_score_summary_table():
    print("\n\U0001F4CA Building round-by-round score summary (total + average)...")

    summary_rows = []
    round_files = sorted(glob.glob("review_output/round*_category_scores.csv"))

    for file in round_files:
        round_number = int(re.search(r'round(\d+)', file).group(1))
        df = pd.read_csv(file)

        row = {"Round": round_number}
        total_scores = {}
        average_scores = {}

        df_final = accumulate_scores(df)  # use true mean per rubric item

        for model in ["gpt-4.1", "gemini-2.5", "claude-3.7"]:
            if model in df_final:
                total = df_final[model].sum()
                avg = df_final[model].mean()
                total_scores[model] = total
                average_scores[model] = avg
                row[f"Total Score ({model})"] = round(total, 1)
                row[f"Average Score ({model})"] = round(avg, 2)
            else:
                row[f"Total Score ({model})"] = "N/A"
                row[f"Average Score ({model})"] = "N/A"

        row["Combined Total"] = round(sum(total_scores.values()), 1)
        row["Combined Average"] = round(sum(average_scores.values()) / len([v for v in average_scores.values() if isinstance(v, (int, float))]), 2)
        summary_rows.append(row)

    if not summary_rows:
        print("\u26A0\ufe0f No score summaries generated!")
        return

    summary_df = pd.DataFrame(summary_rows)
    summary_df.sort_values(by="Round", inplace=True)
    summary_df.to_csv("review_output/score_summary.csv", index=False)
    print("\u2705 Saved: review_output/score_summary.csv")




# === LaTeX Build Function (Revised)
def build_acm_pdf(tex_file: str, bib_file_path: str, output_dir: str, output_name: str):
    os.makedirs(output_dir, exist_ok=True)

    with open(tex_file, "r", encoding="utf-8") as f:
        tex_content = f.read()

    # Extract title
    title_match = re.search(r'\\title\{(.+?)\}', tex_content, re.DOTALL)
    title = title_match.group(1).strip() if title_match else ""

    # Extract abstract
    abstract_match = re.search(r'\\begin\{abstract\}(.+?)\\end\{abstract\}', tex_content, re.DOTALL)
    abstract = abstract_match.group(1).strip() if abstract_match else ""

    # Remove original title, abstract and maketitle
    body = re.sub(r'\\title\{(.+?)\}', '', tex_content, flags=re.DOTALL)
    body = re.sub(r'\\begin\{abstract\}(.+?)\\end\{abstract\}', '', body, flags=re.DOTALL)
    body = re.sub(r'\\maketitle', '', body, flags=re.DOTALL)

    # Assemble clean ACM-style LaTeX
    header = r"""\documentclass[sigconf]{acmart}

\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{multirow}
\usepackage{array}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{adjustbox}
\usepackage{algorithm}
\usepackage{algpseudocode}
\usepackage{float}
\usepackage{xcolor}

\settopmatter{printacmref=true}
\citestyle{acmnumeric}

\title{%s}

\begin{document}

\begin{abstract}
%s
\end{abstract}

\maketitle
""" % (title, abstract)

    footer = r"""
\bibliographystyle{ACM-Reference-Format}
\bibliography{references}
\end{document}
"""

    final_tex = header + "\n" + body.strip() + "\n" + footer

    # Save the cleaned .tex
    tex_output_path = os.path.join(output_dir, f"{output_name}.tex")
    with open(tex_output_path, "w", encoding="utf-8") as f:
        f.write(final_tex)

    # Copy bibliography file
    bib_output_path = os.path.join(output_dir, "references.bib")
    try:
        shutil.copyfile(bib_file_path, bib_output_path)
    except Exception as e:
        print(f"❌ Failed to copy bibliography file: {e}")

    # Compile LaTeX
    compile_steps = [
        ["pdflatex", "-interaction=nonstopmode", f"{output_name}.tex"],
        ["bibtex", f"{output_name}"],
        ["pdflatex", "-interaction=nonstopmode", f"{output_name}.tex"],
        ["pdflatex", "-interaction=nonstopmode", f"{output_name}.tex"],
    ]

    try:
        for cmd in compile_steps:
            try:
                subprocess.run(cmd, cwd=output_dir, check=True)
            except subprocess.CalledProcessError as e:
                print(f"⚠️ Warning: minor LaTeX issue during {cmd}")

        if os.path.exists(os.path.join(output_dir, f"{output_name}.pdf")):
            print(f"✅ PDF built: {output_dir}/{output_name}.pdf")
        else:
            print(f"❌ PDF not generated. Check {output_name}.log for errors.")
    except Exception as e:
        print(f"❌ Build failed: {e}")


def accumulate_scores(df):
    """
    Input: df with columns ["Model","Category","Sub-Criterion","Score (1–5)",…]
    Output: pivoted DataFrame indexed by (Category, Sub-Criterion) with columns
            ["gpt-4.1","gemini-2.5","claude-3.7"] containing the mean score per item.
    """
    # 1. ensure numeric
    df["Score"] = pd.to_numeric(df["Score (1–5)"], errors="coerce")
    df = df.dropna(subset=["Score"])

    # 2. average per Model × Category × Sub-Criterion
    grouped = (
        df
        .groupby(["Model","Category","Sub-Criterion"])["Score"]
        .mean()
        .round(2)
        .reset_index()
    )

    # 3. pivot so each model becomes a column
    pivot = (
        grouped
        .pivot(index=["Category","Sub-Criterion"], columns="Model", values="Score")
    )

    return pivot

# === Scoring & Round Constants ===
MAX_ROUNDS = 4
TOTAL_SUBCRITERIA = 20
MAX_SCORE_PER_CRITERION = 5
NUM_MODELS = 3
TARGET_PERCENT = 0.90  # 90%

MAX_TOTAL_SCORE = TOTAL_SUBCRITERIA * MAX_SCORE_PER_CRITERION * NUM_MODELS
TARGET_TOTAL_SCORE = MAX_TOTAL_SCORE * TARGET_PERCENT

initial_tex = "survey_paper.tex"
initial_bib = "references.bib"
pdf_input_path = "pdf_output/final_paper_round0.pdf"
round_num = 0

print(f"\n🎯 Max total score: {MAX_TOTAL_SCORE}, Target (90%): {TARGET_TOTAL_SCORE:.1f}")

# === Step 0: Build Initial PDF ===
print("\n🚀 Building initial paper...")
build_acm_pdf(
    tex_file=initial_tex,
    bib_file_path=initial_bib,
    output_dir="pdf_output",
    output_name="final_paper_round0"
)

# === Self-Improvement Loop ===
# === Self-Improvement Loop ===
while round_num < MAX_ROUNDS:
    print(f"\n🔁 Round {round_num}: Reviewing and Improving")

    # Step 1: chunked review
    reviews = review_paper_by_chunks(pdf_input_path)
    if not reviews:
        print(f"⚠️ No valid reviews for round {round_num}. Skipping.")
        break

    # Step 2: Save raw chunked outputs
    df_raw     = pd.DataFrame(reviews["category_scores"])
    df_sections= pd.DataFrame(reviews["section_feedback"])
    df_overall = pd.DataFrame(reviews["overall_evaluation"])
    df_raw.to_csv(f"review_output/round{round_num}_category_scores.csv", index=False)
    df_sections.to_csv(f"review_output/round{round_num}_section_feedback.csv", index=False)
    df_overall.to_csv(f"review_output/round{round_num}_overall_evaluation.csv", index=False)
    print(f"✅ Saved all reviews for round {round_num}")

    # --- NEW Step 3: compute per-criterion means and true totals ---
    # (you need to have defined accumulate_scores(df_raw) somewhere)
    df_final = accumulate_scores(df_raw)
    total_scores = {}
    for model in ["gpt-4.1", "gemini-2.5", "claude-3.7"]:
        if model in df_final:
            # sum the 20 averaged sub-criteria → 0–100
            total = df_final[model].sum()
        else:
            total = 0
        total_scores[model] = total
        print(f"📊 Total Score ({model}): {total:.1f} / 100.0")

    combined_total = sum(total_scores.values())
    print(f"📈 Combined Total Score (3-agent): {combined_total:.1f} / {MAX_TOTAL_SCORE}")

    # log & stopping
    with open("review_output/total_score.txt", "a") as f:
        f.write(f"Round {round_num}: {combined_total:.1f}\n")

    if combined_total >= TARGET_TOTAL_SCORE:
        print("🎯 Target Total Score Reached! Ending self-improvement early.")
        break

    # … rest of your loop (improve → rebuild → increment round_num) …
 #Step 4: Improve LaTeX based on reviews
    # Step 4: Improve LaTeX based on reviews
    # Step 4: Prepare global feedback summary for all sections
    low_scores_df = df_raw[df_raw["Score (1–5)"] < 5]

    # Drop duplicates by (Model, Category, Sub-Criterion) to keep most relevant issues
    unique_feedback_df = low_scores_df.drop_duplicates(subset=["Model", "Category", "Sub-Criterion"])

    # Convert to JSON
    review_feedback_json = unique_feedback_df.to_json(orient="records")


    tex_to_improve = "survey_paper.tex" if round_num == 0 else f"output/final_round{round_num-1}_paper.tex"

    citation_summary_dict = load_citation_summaries_by_refkey("summaries_dedup.csv")
    
    improve_latex_file(
    tex_path=tex_to_improve,
    round_num=round_num,
    citation_summary_dict=citation_summary_dict
)




    # Step 5: Build PDF for the next round
    build_acm_pdf(
        tex_file=f"output/final_round{round_num}_paper.tex",
        bib_file_path=initial_bib,
        output_dir="pdf_output",
        output_name=f"final_paper_round{round_num+1}"
    )

    # Step 6: Update pdf path for next review
    pdf_input_path = f"pdf_output/final_paper_round{round_num+1}.pdf"
    round_num += 1

print("\n✅ Finished Self-Improvement Cycle!")
# --- Call it ---
build_score_summary_table()

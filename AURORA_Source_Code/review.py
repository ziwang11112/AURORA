import os
import re
import json
import shutil
import subprocess
import pandas as pd
import warnings
from dotenv import load_dotenv
from crewai import Agent, Crew, Process, Task, LLM
from PyPDF2 import PdfReader
from crewai.tools import BaseTool

warnings.filterwarnings('ignore')

# === Load Environment
load_dotenv()
os.environ["MODEL"] = "gpt-4.1"
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
llm_gpt = LLM(model="gpt-4.1", temperature=0)
llm_gemini = LLM(model="gemini/gemini-2.5-pro-preview-03-25", temperature=0)

# === Define PDF Reader
class PDFReadertool(BaseTool):
    name: str = "pdf_reader"
    description: str = "Read a local PDF file."
    def _run(self, pdf_path: str, page_limit: int = 1000):
        try:
            reader = PdfReader(pdf_path)
            return "\n\n".join([page.extract_text() for page in reader.pages[:page_limit] if page.extract_text()])
        except Exception as e:
            return f"Error reading PDF: {e}"

pdf_reader_tool = PDFReadertool()

# Monkey-patch Crew output
original_kickoff = Crew.kickoff
def safe_kickoff(self, *args, **kwargs):
    result = original_kickoff(self, *args, **kwargs)
    return getattr(result, "output", str(result))
Crew.kickoff = safe_kickoff

# === Define Reviewers
reviewer_agent_gpt = Agent(
    role="Survey Reviewer GPT-4",
    goal="Review academic survey using rubric.",
    verbose=True,
    model=llm_gpt,
    tools=[pdf_reader_tool],
    allow_delegation=False,
    memory=False
)

reviewer_agent_gemini = Agent(
    role="Survey Reviewer Gemini",
    goal="Review academic survey using rubric.",
    verbose=True,
    model=llm_gemini,
    tools=[pdf_reader_tool],
    allow_delegation=False,
    memory=False
)

# === Review Task
def structured_review_task(paper_content: str) -> Task:
    instruction = (
        f"Evaluate:\n{paper_content}\n\n"
        "Score: Scope, Literature, Analysis, Originality, Organization, Presentation, References, Ethics.\n"
        "Also for each Section (1,2,3.1,...): Strengths, Weaknesses, Improvement Suggestions.\n"
        "Output: Strict JSON list (scores + comments + overall evaluation).\n"
    )
    return Task(description=instruction, expected_output="JSON review", agent=None, model=None, human_input=False)

def review_paper(pdf_path):
    all_reviews = []
    pdf_text = pdf_reader_tool.run(pdf_path)
    if not pdf_text or "Error" in pdf_text:
        return None
    for agent, name in [(reviewer_agent_gpt, "gpt-4.1"), (reviewer_agent_gemini, "gemini-2.5")]:
        print(f"🧠 {name} Reviewing...")
        task = structured_review_task(pdf_text)
        task.agent = agent
        task.model = agent.model
        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential)
        result = crew.kickoff()
        try:
            rows = json.loads(result)
            for row in rows:
                row['Model'] = name
            all_reviews.extend(rows)
        except Exception as e:
            print(f"⚠️ Error parsing {name} review: {e}")
    return all_reviews

# === Define Improvement Agent
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
def improve_paper_task(paper_content: str, review_feedback: str) -> Task:
    return Task(
        description=(
            "You are given the following LaTeX paper content and structured reviewer feedback in JSON format.\n\n"
            f"--- PAPER CONTENT START ---\n{paper_content}\n--- PAPER CONTENT END ---\n\n"
            f"--- REVIEW FEEDBACK START ---\n{review_feedback}\n--- REVIEW FEEDBACK END ---\n\n"
            "Your tasks are:\n"
            "- Focus only on improving sections where scores are below 4/5.\n"
            "- Revise for clarity, depth, logical flow, LaTeX formatting, and citation accuracy.\n"
            "- **Do NOT modify citation styles**: Always preserve original citation format (e.g., `~\\cite{ref101,ref102}`).\n"
            "- **Do NOT insert any new figures** unless they already exist in the original.\n"
            "- **Table handling (MANDATORY for all tables):**\n"
            "    • Enclose every table inside:\n"
            "        \\begin{table*}[htbp]\n"
            "        \\centering\n"
            "        \\caption{<insert caption text>}\n"
            "        \\label{<insert label>}\n"
            "        \\begin{adjustbox}{max width=\\textwidth}\n"
            "        \\begin{tabular}{@{}llll@{}}\n"
            "        \\toprule\n"
            "        ... table content ...\n"
            "        \\bottomrule\n"
            "        \\end{tabular}\n"
            "        \\end{adjustbox}\n"
            "        \\end{table*}\n"
            "- Always maintain valid LaTeX syntax.\n"
            "- Never change or reinterpret scientific contributions.\n\n"
            "**Important**: Only output the fully improved LaTeX text. No extra explanation. No additional notes."
        ),
        expected_output="Fully improved LaTeX content, compliant with strict formatting and citation preservation.",
        agent=improvement_agent,
        model=llm_gpt,
        human_input=False
    )



# === LaTeX Helpers
def extract_latex_title(text): return re.search(r'\\title\{(.+?)\}', text, re.DOTALL).group(1).strip()
def extract_abstract(text): return re.search(r'\\begin\{abstract\}(.+?)\\end\{abstract\}', text, re.DOTALL).group(0)
def remove_original_preamble(text):
    text = re.sub(r'(?s)\\title\{.*?\}\s*\\maketitle', '', text)
    text = re.sub(r'(?s)\\begin\{abstract\}.*?\\end\{abstract\}', '', text)
    return text.strip()
def split_latex_by_sections(text):
    pattern = re.compile(r'\\(section|subsection|subsubsection)\*?\{(.+?)\}', re.MULTILINE)
    matches = list(pattern.finditer(text))
    sections = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i+1].start() if i+1 < len(matches) else len(text)
        sections.append({"type": m.group(1), "title": m.group(2), "content": text[start:end].strip()})
    return sections

def improve_latex_file(tex_path, review_feedback, output_path):
    with open(tex_path, "r", encoding="utf-8") as f:
        content = f.read()
    title = extract_latex_title(content)
    abstract = extract_abstract(content)
    body = remove_original_preamble(content)
    sections = split_latex_by_sections(body)
    improved = []
    for sec in sections:
        print(f"🛠 Improving section: {sec['title']}")
        task = improve_paper_task(sec['content'], review_feedback)
        crew = Crew(agents=[improvement_agent], tasks=[task], process=Process.sequential)
        improved_section = crew.kickoff()
        improved.append(improved_section)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"\\title{{{title}}}\n\\maketitle\n\n{abstract}\n\n" + "\n\n".join(improved))

def build_pdf(tex_file, bib_file, output_dir, output_name):
    os.makedirs(output_dir, exist_ok=True)
    shutil.copyfile(tex_file, os.path.join(output_dir, f"{output_name}.tex"))
    shutil.copyfile(bib_file, os.path.join(output_dir, "references.bib"))
    steps = [
        ["pdflatex", "-interaction=nonstopmode", f"{output_name}.tex"],
        ["bibtex", output_name],
        ["pdflatex", "-interaction=nonstopmode", f"{output_name}.tex"],
        ["pdflatex", "-interaction=nonstopmode", f"{output_name}.tex"],
    ]
    try:
        for cmd in steps:
            subprocess.run(cmd, cwd=output_dir, check=True)
        print(f"✅ PDF built: {output_dir}/{output_name}.pdf")
    except Exception as e:
        print(f"❌ Build failed: {e}")

def compute_agreement(df):
    df_gpt = df[df["Model"] == "gpt-4.1"]
    df_gemini = df[df["Model"] == "gemini-2.5"]
    common = pd.merge(df_gpt, df_gemini, on=["Category", "Sub-Criterion"], suffixes=("_gpt", "_gemini"))
    if len(common) == 0: return 0
    return round((common["Score (1–5)_gpt"] == common["Score (1–5)_gemini"]).sum() / len(common) * 100, 2)

# === Main Self-Improvement Loop
MAX_ROUNDS = 5
TARGET_AGREEMENT = 90.0
initial_tex = "survey_paper.tex"
initial_bib = "references.bib"

# Build initial
print("\n🚀 Building initial...")
build_pdf(initial_tex, initial_bib, "pdf_output", "final_paper_round0")
pdf_input_path = "pdf_output/final_paper_round0.pdf"
round_num = 0

while round_num < MAX_ROUNDS:
    print(f"\n🔁 Round {round_num}: Reviewing and Improving")
    reviews = review_paper(pdf_input_path)
    if not reviews: break
    df = pd.DataFrame(reviews)
    df.to_csv(f"review_output/round{round_num}_reviews.csv", index=False)
    agreement = compute_agreement(df)
    print(f"📊 Cross-Model Agreement: {agreement}%")
    with open("review_output/agreement_score.txt", "a") as f:
        f.write(f"Round {round_num}: {agreement}%\n")
    if agreement >= TARGET_AGREEMENT:
        print("🎯 Target Reached!")
        break
    review_feedback = df.to_json(orient="records")
    tex_to_improve = "survey_paper.tex" if round_num == 0 else "output/final_polished_research_paper.tex"
    improve_latex_file(tex_to_improve, review_feedback, "output/final_polished_research_paper.tex")
    build_pdf("output/final_polished_research_paper.tex", initial_bib, "pdf_output", f"final_paper_round{round_num+1}")
    pdf_input_path = f"pdf_output/final_paper_round{round_num+1}.pdf"
    round_num += 1

print("\n✅ Finished Self-Improvement Cycle!")

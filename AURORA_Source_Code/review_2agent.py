import os
import json
import json5
import pandas as pd
import warnings
from dotenv import load_dotenv
from crewai import Agent, Crew, Process, Task, LLM
from PyPDF2 import PdfReader
from crewai.tools import BaseTool
from tqdm import tqdm

warnings.filterwarnings('ignore')

# === Load Environment
load_dotenv()

# === Setup
papers_folder = "output"
output_folder = "review_aurora"
os.makedirs(output_folder, exist_ok=True)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY")
SERPER_API_KEY    = os.getenv("SERPER_API_KEY")
print("✅ Loaded API keys")

llm_gpt     = LLM(model="gpt-4.1", temperature=0)
llm_gemini  = LLM(model="gemini/gemini-2.5-pro-preview-03-25", temperature=0)
llm_claude = LLM(
    model="claude-3-7-sonnet-20250219",  # or "claude-3-7-sonnet-20250219" depending on your provider
    temperature=0
)
 
# === Monkey patch Crew kickoff
from crewai import Crew
original_kickoff = Crew.kickoff
def safe_kickoff(self, *args, **kwargs):
    result = original_kickoff(self, *args, **kwargs)
    return getattr(result, "output", str(result))
Crew.kickoff = safe_kickoff

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

# === Define Agents
reviewer_agent_claude = Agent(
    role="Survey Reviewer Claude",
    goal="Review academic paper using strict rubric.",
    backstory="A rigorous academic evaluator with a balance of reasoning and clarity.",
    verbose=True,
    model=llm_claude,
    tools=[],
    allow_delegation=False,
    memory=False
)

reviewer_agent_gpt = Agent(
    role="Survey Reviewer GPT-4.1",
    goal="Review academic paper using strict rubric.",
    backstory="An experienced academic peer reviewer specializing in evaluating survey papers.",
    verbose=True,
    model=llm_gpt,
    tools=[ ],
    allow_delegation=False,
    memory=False
)
reviewer_agent_gemini = Agent(
    role="Survey Reviewer Gemini",
    goal="Review academic paper using strict rubric.",
    backstory="An experienced academic peer reviewer specializing in evaluating survey papers.",
    verbose=True,
    model=llm_gemini,
    tools=[ ],
    allow_delegation=False,
    memory=False
)

# === Load your full detailed rubric JSON
with open("full_detailed_review_rubric.json") as f:
    FULL_RUBRIC = json.load(f)

# === Helper: Generate prompt blocks from rubric
def generate_rubric_prompt_blocks(rubric_dict):
    out = ""
    for category, submap in rubric_dict.items():
        out += f"{category}:\n"
        for subcrit, scores in submap.items():
            out += f"  {subcrit}:\n"
            for score in sorted(scores.keys(), key=int, reverse=True):
                guidance = scores[score]
                out += f"    - {score}: {guidance}\n"
            out += "\n"
    return out.strip()

# === Review Task Factory


def attempt_repair(raw_output: str) -> str:
    if not isinstance(raw_output, str): return raw_output
    keys = [k for cat in FULL_RUBRIC.values() for k in cat.keys()]
    for key in keys:
        raw_output = raw_output.replace(f'"{key}":', f'{{"item": "{key}", "score":')
    raw_output = raw_output.replace('}', ', "comment": "No comment"}')
    return raw_output



def parse_score_block(block, chunk_label=None, agent_name=None):
    rows = []
    category = block.get("category", "").strip().title()
    category_comment = block.get("comment", "")
    criteria = block.get("criteria", [])
    context = f"[{chunk_label or '?'} | {agent_name or '?'} | {category}]"
    seen_items = set()

    if not isinstance(criteria, list):
        log(f"⚠️ {context} Skipping block: criteria is not a list → {criteria}")
        return rows

    for crit in criteria:
        if not isinstance(crit, dict):
            log(f"⚠️ {context} Skipping non-dict criterion: {crit}")
            continue

        if ("item" in crit or "name" in crit) and "score" in crit:
            item_key = "item" if "item" in crit else "name"
            item = str(crit[item_key]).strip().title()
            seen_items.add(item)
            try:
                score = float(crit["score"])
                comment = crit.get("comment", category_comment)
                log(f"✅ {context} Parsed [Standard]: {item} = {score}")
                rows.append({
                    "category": category,
                    "item": item,
                    "score": score,
                    "comment": comment
                })
            except Exception as e:
                log(f"❌ {context} Failed to parse score for {item}: {e}")

        elif "comment" in crit and len(crit) > 1:
            comment = crit["comment"]
            for k, v in crit.items():
                if k == "comment":
                    continue
                item = str(k).strip().title()
                seen_items.add(item)
                try:
                    score = float(v)
                    log(f"✅ {context} Parsed [Gemini-style]: {item} = {score}")
                    rows.append({
                        "category": category,
                        "item": item,
                        "score": score,
                        "comment": comment
                    })
                except Exception as e:
                    log(f"❌ {context} Failed to parse Gemini-style score for {item}: {e}")

        elif len(crit) == 1:
            for k, v in crit.items():
                item = str(k).strip().title()
                seen_items.add(item)
                try:
                    score = float(v)
                    log(f"✅ {context} Parsed [Minimal]: {item} = {score}")
                    rows.append({
                        "category": category,
                        "item": item,
                        "score": score,
                        "comment": category_comment
                    })
                except Exception as e:
                    log(f"❌ {context} Failed to parse minimal score for {item}: {e}")

        else:
            log(f"⚠️ {context} Unrecognized format: {crit}")

    # 🔍 Check for missing rubric items
    expected_items = list(FULL_RUBRIC.get(category, {}).keys())
    for expected in expected_items:
        if expected.strip().title() not in seen_items:
            log(f"⚠️ {context} MISSING expected rubric item: '{expected}'")

    return rows
   
def chunk_pdf_by_n_pages(pdf_path, n=2, max_pages=100):
    """
    Chunk the PDF into groups of `n` pages for better context in review tasks.
    
    Returns:
        List of (chunk_label, combined_text, starting_page_index)
    """
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


# === Chunked Review Task Factory ===
def structured_review_task_chunk(chunk_text, chunk_label):
    rubric_guidance = generate_rubric_prompt_blocks(FULL_RUBRIC)
    return Task(
        description=(
            f"You are reviewing a specific section of a survey paper labeled: **{chunk_label}**.\n\n"
            f"=== CHUNK CONTENT START ===\n{chunk_text}\n=== CHUNK CONTENT END ===\n\n"
            "Refer to the detailed evaluation rubric below and assess as many criteria as are reasonably inferable from this section:\n\n"
            f"{rubric_guidance}\n\n"
            "Your output must follow this exact JSON structure:\n\n"
            "{\n"
            '  "scores": [\n'
            "    {\n"
            '      "category": "Scope",\n'
            '      "criteria": [\n'
            '        {"item": "Objectives", "score": 1-5, "comment": "Explanation"},\n'
            '        {"item": "Relevance",  "score": 1-5, "comment": "Explanation"},\n'
            '        {"item": "Audience",   "score": 1-5, "comment": "Explanation"}\n'
            "      ],\n"
            '      "comment": "Overall category comment"\n'
            "    },\n"
            "    ...\n"
            "  ]\n"
            "}\n\n"
            "Formatting rules:\n"
            "• Use only double quotes for all keys and string values.\n"
            "• Every criterion must be a dictionary with keys 'item', 'score', and 'comment'.\n"
            "• Do not use formats like {'Objectives': 5} or any other shorthand.\n"
            "• Output strictly one JSON object. No markdown, no extra text.\n"
            "• Do not include trailing commas or explanatory text."
        ),
        expected_output="Valid JSON structured by rubric, with 'item', 'score', and 'comment' format.",
        agent=None,
        model=None,
        human_input=False
    )

# === Per-Paper Review Over Chunks ===
def review_paper_chunked(pdf_path):
    chunks = chunk_pdf_by_n_pages(pdf_path, n=3)
    all_rows = []
    for chunk_label, chunk_text, chunk_idx in chunks:
        for agent, name in [(reviewer_agent_gpt, "gpt-4.1"), (reviewer_agent_gemini, "gemini-2.5"), (reviewer_agent_claude, "claude-3.7")]:
            task = structured_review_task_chunk(chunk_text, chunk_label)
            task.agent = agent
            crew = Crew(agents=[agent], tasks=[task], process=Process.sequential)
            out = crew.kickoff()
            try:
                parsed = json.loads(out) if isinstance(out, str) else out
            except:
                try:
                    repaired = attempt_repair(out)
                    parsed = json.loads(repaired)
                except Exception as e:
                    parsed = json5.loads(out)

            for block in parsed.get("scores", []):
                for row in parse_score_block(block, chunk_label=chunk_label, agent_name=name):
                    row.update({
                        "agent": name,
                        "chunk": chunk_label,
                        "chunk_index": chunk_idx
                    })
                    all_rows.append(row)
    return pd.DataFrame(all_rows)

# === Accumulate Per-Criterion Scores ===
def accumulate_scores(df):
    # ← ADD THESE TWO LINES
    df['score'] = pd.to_numeric(df['score'], errors='coerce')
    df = df.dropna(subset=['score'])

    grouped = (
        df
        .groupby(["agent", "category", "item"])["score"]
        .mean()
        .round(2)
        .reset_index()
    )
    return (
        grouped
        .pivot_table(index=["category", "item"], columns="agent", values="score")
        .reset_index()
    )


def compute_chunked_agreement(pivot_df):
    agents = ["gpt-4.1", "gemini-2.5", "claude-3.7"]
    agreement_matrix = {}
    for i in range(len(agents)):
        for j in range(i + 1, len(agents)):
            a1, a2 = agents[i], agents[j]
            agree_mask = pivot_df[a1] == pivot_df[a2]
            agreement_pct = (agree_mask.sum() / len(agree_mask)) * 100
            agreement_matrix[f"{a1} vs {a2}"] = round(agreement_pct, 2)
            # Use 1 (agree) and 0 (disagree) instead of emoji
            pivot_df[f"Agree ({a1} vs {a2})"] = agree_mask.astype(int)
    return agreement_matrix, pivot_df




def compute_comparison(results):
    agents = ["gpt-4.1", "gemini-2.5", "claude-3.7"]
    comparisons = []
    for i in range(len(agents)):
        for j in range(i + 1, len(agents)):
            a1, a2 = agents[i], agents[j]
            df1 = pd.DataFrame(results[a1])
            df2 = pd.DataFrame(results[a2])
            merged = pd.merge(df1, df2, on=["category", "item"], suffixes=(f"_{a1}", f"_{a2}"))
            for _, row in merged.iterrows():
                score_a1 = row[f"score_{a1}"]
                score_a2 = row[f"score_{a2}"]
                agreement = float(score_a1) == float(score_a2)
                comparisons.append({
                    "Category": row["category"],
                    "Sub-Criterion": row["item"],
                    f"Score ({a1})": score_a1,
                    f"Score ({a2})": score_a2,
                    "Agreement": agreement,
                    "Pair": f"{a1} vs {a2}"
                })
    return pd.DataFrame(comparisons)



# === Main Loop
# === Main Loop
import os
import subprocess
from tqdm import tqdm
import pandas as pd
from datetime import datetime

log_path = os.path.join(output_folder, "process.log")
log_file = open(log_path, "a", encoding="utf-8")

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {msg}"
    print(log_line)
    log_file.write(log_line + "\n")
    log_file.flush()

# === Convert all .md to .pdf first ===
for fname in os.listdir(papers_folder):
    if fname.endswith(".md"):
        stem = os.path.splitext(fname)[0]
        md_path = os.path.join(papers_folder, fname)
        pdf_path = os.path.join(papers_folder, f"{stem}.pdf")
        try:
            subprocess.run(["pandoc", md_path, "-o", pdf_path], check=True)
            log(f"✅ Converted {fname} → {stem}.pdf")
        except subprocess.CalledProcessError as e:
            log(f"❌ Failed to convert {fname}: {e}")

# === Review all PDFs ===
all_results = []
for fname in tqdm(os.listdir(papers_folder), desc="📄 Processing Papers"):
    if not fname.lower().endswith(".pdf"): continue
    path = os.path.join(papers_folder, fname)
    log(f"\n🔍 Reviewing {fname} (chunked)...")
    try:
        df_chunks = review_paper_chunked(path)
        df_final = accumulate_scores(df_chunks)
        agreement_pct, agreement_df = compute_chunked_agreement(df_final)

        total_row = {
        "category": "TOTAL",
        "item": "",
        "gpt-4.1": df_final["gpt-4.1"].sum() if "gpt-4.1" in df_final else 0,
        "gemini-2.5": df_final["gemini-2.5"].sum() if "gemini-2.5" in df_final else 0,
        "claude-3.7": df_final["claude-3.7"].sum() if "claude-3.7" in df_final else 0,
        "Agreement": ""
        }

        df_final = pd.concat([df_final, pd.DataFrame([total_row])], ignore_index=True)
        df_final["Paper Name"] = fname

        out_csv = os.path.join(output_folder, f"{os.path.splitext(fname)[0]}_chunked_review.csv")
        df_final.to_csv(out_csv, index=False, encoding='utf-8-sig')
        all_results.append(df_final)

        log(f"✅ Saved chunked review for {fname} — Agreement matrix: {agreement_pct}")

    except Exception as e:
        log(f"❌ Error reviewing {fname}: {e}")

# === Save combined results ===
if all_results:
    combined = pd.concat(all_results, ignore_index=True)
    combined_csv_path = os.path.join(output_folder, "all_papers_combined_review.csv")

    if os.path.exists(combined_csv_path):
        log("🔁 Existing combined file found. Appending results...")
        existing_df = pd.read_csv(combined_csv_path)
        combined = pd.concat([existing_df, combined], ignore_index=True)

    log(f"📦 Number of papers processed in this run: {len(all_results)}")
    log(f"🧾 Total Combined DataFrame rows: {len(combined)}")

    combined.to_csv(combined_csv_path, index=False)
    log(f"\n📚 Results appended to {combined_csv_path}")
    
    
log_file.close()

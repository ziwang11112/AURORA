import os
import warnings
warnings.filterwarnings('ignore')

 
 
import re
 
 
from dotenv import load_dotenv
load_dotenv()


# ... Rest of your main script code that uses these variables and tools ...

# Continue using these variables for initialization...

# Continue using these variables for initialization of CrewAI, etc.
from crewai import LLM, Agent, Crew, Task
from crewai import Crew, Process, Agent, Task
# Import and initialize tools from crewai_tools
from crewai_tools import (
    FileReadTool,
    CSVSearchTool,
    ScrapeWebsiteTool,
    MDXSearchTool,
    SerperDevTool,
    TXTSearchTool,
    PDFSearchTool,
    DirectoryReadTool,
    RagTool,
    WebsiteSearchTool,
)
# Initialize desired tools
search_tool = SerperDevTool()
scrape_tool = ScrapeWebsiteTool()
# Optionally, reinitialize FileReadTool if needed:

 
# ------------------------------
# Initialize Environment Variables
# ------------------------------
journal_name = os.environ.get("JOURNAL")
 
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")

os.environ["MODEL"] = 'gpt-4.1-mini'

llm = LLM(model="gpt-4.1-mini", temperature=0)

import requests
import pandas as pd
import re
import asyncio
from typing import List


def safe_extract_output(result):
    if isinstance(result, list):
        return result[0] if result else ""
    return getattr(result, "output", str(result) if result is not None else "")



# Monkey-patch Crew.kickoff to auto-extract clean output
from crewai import Crew

original_kickoff = Crew.kickoff

def safe_kickoff(self, *args, **kwargs):
    result = original_kickoff(self, *args, **kwargs)
    return safe_extract_output(result)

Crew.kickoff = safe_kickoff


"""" 
# Load the reordered summaries CSV file
input_file = "summaries_dedup.csv"
output_file = "citation.csv"

# Read the CSV
df = pd.read_csv(input_file)

# Extract the required columns
citation_df = df[['Index', 'Citation']]

# Save to a new CSV file
citation_df.to_csv(output_file, index=False, encoding="utf-8")

print(f"Saved Index and Citation columns to {output_file}")
"""


# Define the AI-powered BibTeX conversion agent
bibtex_agent = Agent(
    role="BibTeX Converter",
    goal="Convert individual citation entries from CSV into properly formatted BibTeX entries, fetching missing details if necessary.",
    verbose=True,
    model=llm,
    tools=[search_tool, scrape_tool],
    backstory=(
        "You specialize in academic referencing and BibTeX formatting. "
        "You ensure that citations are correctly formatted based on journal/conference/book sources, "
        "assigning the appropriate BibTeX entry type (@article, @inproceedings, @book, etc.). "
        "If information is missing, you search online using citation details."
    ),
    allow_delegation=False
)

def fetch_reference_info(title):
    """
    Search for missing reference details online using the paper title.
    First tries CrossRef, then PubMed if necessary.
    """
    search_urls = [
        f"https://api.crossref.org/works?query.title={title}",
        f"https://pubmed.ncbi.nlm.nih.gov/?term={title.replace(' ', '+')}"
    ]
    
    for search_url in search_urls:
        try:
            response = requests.get(search_url)
            if response.status_code == 200:
                data = response.json()
                if "message" in data and "items" in data["message"]:
                    best_match = data["message"]["items"][0]
                    return {
                        "author": ", ".join([a["family"] for a in best_match.get("author", [])]),
                        "journal": best_match.get("container-title", [""])[0],
                        "volume": best_match.get("volume", ""),
                        "year": best_match.get("published-print", {}).get("date-parts", [[None]])[0][0],
                        "url": best_match.get("URL", ""),
                        "doi": best_match.get("DOI", ""),
                    }
        except Exception as e:
            print(f"Error fetching data: {e}")
    
    return {}

def bibtex_agent_task(index, citation):
    """
    Convert a single citation into a properly formatted BibTeX entry.
    """
    task = Task(
        description=(
            f"Convert and validate the following citation into a properly formatted BibTeX entry:\n\n"
            f"Index: {index}\n"
            f"Citation: {citation}\n\n"
            "ensure the correct citation information."
            "Ensure the entry follows proper BibTeX format and uses the correct entry type (@article, @inproceedings, @misc, etc.). "
            "Use the reference number as the BibTeX key, e.g., @article{ref1, ...} for Index 1, @article{ref2, ...} for Index 2, etc. "
            "If the citation is from a webpage, use @misc or @online instead of @article and include only relevant fields (e.g., author, title, URL, access date). "
            "Do NOT search online if optional details like DOI, volume, or journal name are missing. "
            "Only search online if essential details (e.g., author, title, year) are completely missing and cannot be inferred from the citation. "
            "Return only the properly formatted BibTeX entry, without additional explanations."
            "\n\n# Output Template:\n"
            "@article{{ref{index},\n"
            "  author    = {{...}},\n"
            "  title     = {{...}},\n"
            "  journal   = {{...}},\n"
            "  year      = ..., \n"
            "  volume    = ..., \n"
            "  number    = ..., \n"
            "  pages     = ..., \n"
            "  doi       = {{...}}, \n"
            "  url       = {{...}} \n"
            "}}\n"
            "\n# Example for Webpage:\n"
            "@misc{{ref{index},\n"
            "  author    = {{...}},\n"
            "  title     = {{...}},\n"
            "  howpublished = {{Online}},\n"
            "  url       = {{...}},\n"
            "  note      = {{Accessed: YYYY-MM-DD}}\n"
            "}}"
        ),
        expected_output="A properly formatted BibTeX entry with the reference number as its key.",
        agent=bibtex_agent,
        model=llm
    )
    return task  
import sys

# File paths
LOG_FILE = "reference_log.txt"
ERROR_LOG_FILE = "error_log.txt"
BIB_FILE = "references.bib"

# ✅ Open log file for writing
log_file = open(LOG_FILE, "w")

# ✅ Redirect sys.stdout to both console and file
class Logger(object):
    def __init__(self, log_file):
        self.terminal = sys.__stdout__  # Console
        self.log = log_file  # Log file

    def write(self, message):
        self.terminal.write(message)  # Print to console
        self.log.write(message)  # Save to file

    def flush(self):
        self.terminal.flush()
        self.log.flush()

# ✅ Apply the custom logging to sys.stdout
sys.stdout = Logger(log_file)

# ✅ Test output
print("✅ Now printing to both console and log file!")

# ✅ Close the log file when done (optional)
# log_file.close()  # Uncomment when script is finished
import re
import requests
import pandas as pd
import sys
from datetime import datetime



def clean_bibtex_output(raw_bibtex):
    """
    Cleans and extracts only valid BibTeX content.
    """
    clean_entry = re.sub(r'Final Answer:\s*', '', raw_bibtex).strip()
    match = re.search(r"```bibtex\n(.*?)\n```", clean_entry, re.DOTALL)
    if match:
        clean_entry = match.group(1).strip()
    clean_entry = re.sub(r'^.*?(?=@)', '', clean_entry, flags=re.DOTALL).strip()
    last_brace = clean_entry.rfind('}')
    if last_brace != -1:
        clean_entry = clean_entry[:last_brace+1]  
    return clean_entry.strip()

def process_csv_to_bib(csv_file, bib_file):
    """
    Reads a CSV file, converts citations to BibTeX using an AI agent, and saves them to a .bib file.
    Logs detailed errors for failed entries.
    """
    df = pd.read_csv(csv_file)
    bib_entries = []
    errors = []  # List to store error details
    errors_index = [] 

    for _, row in df.iterrows():
        try:
            index = row["Index"]
            citation = row["Citation"]
            print(f"\nProcessing Index {index}...")

            task = bibtex_agent_task(index, citation)
            crew = Crew(agents=[bibtex_agent], tasks=[task], process=Process.sequential)
            result = crew.kickoff()

            cleaned_bibtex = clean_bibtex_output(result)
            bib_entries.append(cleaned_bibtex)
            print(f"Successfully processed Index {index}.")

        except Exception as e:
            error_message = (
                f"Error processing entry at index {index}:\n"
                f"Citation: {citation}\n"
                f"Exception: {str(e)}\n"
            )
            errors.append(error_message)
            errors_index.append(index)
            print(f"Error encountered at Index {index}. Logging error.")
            continue  # Skip to the next entry

    # Save valid BibTeX entries
    try:
        with open(bib_file, "w", encoding="utf-8") as bibfile:
            bibfile.write("\n\n".join(bib_entries))
        print(f"Successfully saved BibTeX references to {bib_file}")
    except Exception as e:
        print(f"Error writing to {bib_file}: {e}")

    # Save error log to a file
    if errors:
        with open(ERROR_LOG_FILE, "w", encoding="utf-8") as error_log:
            error_log.write("\n\n".join(errors))
        print(f"\nErrors encountered. Detailed log saved to {ERROR_LOG_FILE}.")

# Run the process and restore standard output
""""""
process_csv_to_bib('citation.csv', BIB_FILE)

 
############  rerun error log 


import re
import requests
import pandas as pd
from datetime import datetime

# File paths
ERROR_LOG_FILE = "error_log.txt"
NEW_ERROR_LOG_FILE = "error_log_retry.txt"
BIB_FILE = "references.bib"

def clean_bibtex_output(raw_bibtex):
    """ Cleans and extracts only valid BibTeX content """
    clean_entry = re.sub(r'Final Answer:\s*', '', raw_bibtex).strip()
    match = re.search(r"```bibtex\n(.*?)\n```", clean_entry, re.DOTALL)
    if match:
        clean_entry = match.group(1).strip()
    clean_entry = re.sub(r'^.*?(?=@)', '', clean_entry, flags=re.DOTALL).strip()
    last_brace = clean_entry.rfind('}')
    if last_brace != -1:
        clean_entry = clean_entry[:last_brace+1]
    return clean_entry.strip()

 

def extract_failed_entries_from_error_log(error_log_file):
    """
    Parses the error log file and extracts failed indices along with their citations.
    """
    failed_entries = []
    
    try:
        with open(error_log_file, "r", encoding="utf-8") as file:
            content = file.read()
        
        # Regular expression to capture index and citation text
        error_pattern = re.findall(
            r"Error processing entry at index (\d+):\nCitation: (.*?)\nException:", 
            content, 
            re.DOTALL
        )

        for match in error_pattern:
            index = int(match[0])
            citation = match[1].strip().replace("\n", " ")  # Remove extra newlines
            failed_entries.append((index, citation))

        return failed_entries
    except FileNotFoundError:
        print(f"Error log {error_log_file} not found.")
        return []
    except Exception as e:
        print(f"Unexpected error while reading error log: {e}")
        return []

def retry_failed_entries(error_log_file, bib_file, new_error_log_file):
    """ 
    Reprocess failed citations from the error log, append valid BibTeX entries, 
    and save remaining failures in a new error log.
    """
    failed_entries = extract_failed_entries_from_error_log(error_log_file)

    if not failed_entries:
        print("No errors to reprocess.")
        return

    bib_entries = []
    new_errors = []

    for index, citation in failed_entries:
        try:
            print(f"Reprocessing entry {index}...")
            task = bibtex_agent_task(index, citation)
            crew = Crew(agents=[bibtex_agent], tasks=[task], process=Process.sequential)
            result = crew.kickoff()

            cleaned_bibtex = clean_bibtex_output(result)
            bib_entries.append(cleaned_bibtex)

        except Exception as e:
            new_errors.append(f"Error processing entry at index {index}:\nCitation: {citation}\nException: {str(e)}\n")
            continue  # Skip to the next entry

    # Append successfully reprocessed BibTeX entries
    if bib_entries:
        with open(bib_file, "a", encoding="utf-8") as bibfile:
            bibfile.write("\n\n".join(bib_entries) + "\n")
        print(f"Successfully appended {len(bib_entries)} reprocessed entries to {bib_file}.")

    # Save new errors to a new error log file
    if new_errors:
        with open(new_error_log_file, "w", encoding="utf-8") as error_log:
            error_log.write("\n".join(new_errors) + "\n")
        print(f"Remaining errors saved in {new_error_log_file}.")
    else:
        print("All failed entries successfully reprocessed!")



# Retry failed entries and save new errors

""" """
retry_failed_entries(ERROR_LOG_FILE, BIB_FILE, NEW_ERROR_LOG_FILE)


 
 
import logging
import re
import sys
from crewai import Agent, Task, Crew, Process

# ——— logging setup ———
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)
logger.info("📢 Logging is now working and printing to the console!")

# ——— Agent setup ———
latex_agent = Agent(
    role="LaTeX conversion agent",
    goal="Convert research paper sections into LaTeX format.",
    verbose=True,
    Memory=True,
    tools=[],
    backstory="You are an expert in LaTeX formatting.",
    allow_delegation=True
)

def normalize_title(title: str) -> str:
    cleaned = re.sub(r'[#*]', '', title)
    cleaned = re.sub(r'\bsection\b', '', cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace(":", "")
    match = re.match(r'\s*([\d]+(?:\.[\d]+)*)', cleaned)
    return match.group(1).strip() if match else title.strip()

def latex_conversion_task(journal_latex: str, section_content: str):
    return Task(
        description=(
            f"You are a LaTeX formatting assistant for academic publications in {journal_latex}. "
            f"Your task is to transform the following research section into **clean, valid LaTeX code**, "
            f"with absolutely no rephrasing, summarizing, or interpretation.\n\n"

            "⚠️ You MUST strictly follow **ALL** formatting rules below. If any instruction is disobeyed, the output will be rejected.\n\n"

            "=== HEADING RULES ===\n"
            "- Clean titles:\n"
            "    • Strip any markdown (#), numbering (e.g. '1.2.3'), or labels like 'Section', 'Sec.', colons, or asterisks.\n"
            "- Heading hierarchy:\n"
            "    • Use \\section{...} for top-level sections.\n"
            "    • Use \\subsection{...} for second-level subsections.\n"
            "    • Use \\subsubsection{...} for third-level subsections.\n"
            "- If the content is empty, only return the correct LaTeX heading (no body text).\n\n"

            "=== CITATION RULES ===\n"
            "- Convert ALL citation formats (e.g., [1], [2, 3], \\cite{1}, \\cite{ref:4}, \\cite{references5}) into \\cite{ref1}, \\cite{ref2,ref3}, etc.\n"
            "- Citation keys MUST be in the form 'refN' (e.g., ref6, ref41).\n"
            "- Do NOT use numeric-only keys or variants like 'ref:', 'references', or 'REF-'.\n"
            "- NEVER leave citations in square brackets like [4] or [5,6].\n"
            "- NEVER use \\cite with anything other than properly normalized 'refN' keys.\n\n"


            "=== TABLE RULES ===\n"
            "- Format ALL tables using the following base structure:\n"
            "  \\begin{table*}[htbp]\n"
            "  \\centering\n"
            "  \\caption{<insert caption text>}\n"
            "  \\label{<insert label>}\n"
            "  \\begin{adjustbox}{max width=\\textwidth}\n"
            "  \\begin{tabular}{lll...}  % Choose the number of 'l' columns automatically\n"
            "  \\toprule\n"
            "  ... table rows ...\n"
            "  \\bottomrule\n"
            "  \\end{tabular}\n"
            "  \\end{adjustbox}\n"
            "  \\end{table*}\n\n"
            "- Use only 'l' for column alignment (e.g., l, ll, lll, llll), automatically based on the number of columns.\n"
            "- Do NOT use 'p{...}', 'c', or 'r'.\n"
            "- Remove ALL vertical bars (|), \\hline commands, or legacy tabular styles.\n"
            "- NEVER change or reword cell content.\n\n"

            "=== OUTPUT RULES ===\n"
            "- Do NOT add any Markdown.\n"
            "- Do NOT include explanations, commentary, or extra notes.\n"
            "- Return ONLY valid LaTeX code, clean and complete.\n"
            "- Do NOT wrap the code in triple backticks (```), and do NOT insert any 'Here is your result:' preamble.\n\n"

            f"=== RAW SECTION START ===\n{section_content}\n=== RAW SECTION END ==="
        ),
        expected_output="Final, clean LaTeX code with strict citation, heading, and table compliance. No Markdown or commentary.",
        agent=latex_agent,
        verbose=True,
        model=llm,
        human_input=False
    )



import re

def normalize_citations(text: str) -> str:
    def normalize_key(k):
        k = k.strip()
        k = re.sub(r'^(ref:|references|ref|REF[-:]?)', '', k, flags=re.IGNORECASE)
        k = re.sub(r'\D*(\d+)\D*', r'\1', k)  # Extract digits only
        return f"ref{k}" if k.isdigit() else None

    # === Normalize \cite{...}
    def latex_cite_replace(match):
        keys = match.group(1)
        refs = filter(None, (normalize_key(k) for k in keys.split(',')))
        return f"\\cite{{{', '.join(refs)}}}"

    text = re.sub(r'\\cite\{([^\}]+)\}', latex_cite_replace, text)

    # === Normalize [123], [123, 124]
    def ieee_bracket_replace(match):
        content = match.group(1)
        # Only apply if all comma-separated parts are digits
        if all(re.match(r'\s*\d+\s*$', part) for part in content.split(',')):
            refs = [f"ref{part.strip()}" for part in content.split(',')]
            return f"\\cite{{{', '.join(refs)}}}"
        return match.group(0)  # return original if it's not a pure numeric citation

    text = re.sub(r'\[(\d+(?:\s*,\s*\d+)*)\]', ieee_bracket_replace, text)

    return text




def extract_latex_title(text: str) -> str:
   
    idx = text.find(r'\title')
    if idx == -1:
        return ""
    # find the opening brace after \title
    brace_start = text.find('{', idx)
    if brace_start == -1:
        return ""
    count = 1
    i = brace_start + 1
    # walk forward counting braces
    while i < len(text) and count > 0:
        if text[i] == '{':
            count += 1
        elif text[i] == '}':
            count -= 1
        i += 1
    # extract everything between the matching braces
    content = text[brace_start+1 : i-1].strip()
    # if that content still wraps another \title{…}, peel one more layer
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
    # Remove the title + maketitle
    text = re.sub(r'(?s)\\title\{.*?\}\s*\\maketitle', '', text)

    # Strip out the first abstract environment entirely
    text = re.sub(r'(?s)\\begin\{abstract\}.*?\\end\{abstract\}', '', text)

    # Drop any leftover lines that start with these commands, including usepackage
    text = re.sub(
        r'(?m)^\s*\\(?:documentclass|usepackage|author|date|maketitle).*\n',
        '',
        text
    )

    # Remove any stray begin/end of document or abstract tokens
    text = re.sub(r'\\(?:begin|end)\{(?:document|abstract)\}', '', text)

    return text


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


def process_sections_into_latex(sections: list, journal_name: str) -> list:
    latex_sections = []
    for i, section_content in enumerate(sections, start=1):
        logger.info(f"Processing section {i}/{len(sections)}")

        cleaned_content = normalize_citations(section_content["content"])
        task = latex_conversion_task(journal_name, cleaned_content)
        crew = Crew(agents=[latex_agent], tasks=[task], process=Process.sequential)

        try:
            result = crew.kickoff()
            output = result.output.strip() if hasattr(result, "output") else str(result).strip()

            # ✅ Check if agent actually changed anything
            if cleaned_content.strip() == output.strip():
                logger.warning(f"⚠️ Agent did not change Section {i}. Check prompt compliance.")
            else:
                logger.info(f"✅ Section {i} updated by agent.")

        except Exception as e:
            logger.error(f"❌ Error processing section {i}: {e}")
            continue

        if output:
            latex_sections.append(output)
        else:
            logger.warning(f"⚠️ Warning: Empty LaTeX output for section {i}.")

    return latex_sections


def remove_code_block_markers(latex_output: str) -> str:
    # strip ```latex ... ``` or ``` ... ```
    return re.sub(r'```(?:latex)?|```', '', latex_output).strip()

def read_outline(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()





if __name__ == "__main__":
    file_path = "completed_research_paper.tex"
     

    # 1) Read entire file
    full_text = read_outline(file_path)

    # 1) Pull out title and abstract from the *original* full_text
    title    = extract_latex_title(full_text)
    abstract = extract_abstract(full_text)

    # 2) Grab only what's between the first \begin{document} and \end{document}
    m = re.search(r'\\begin\{document\}(.*)\\end\{document\}', full_text, re.DOTALL)
    doc_body = m.group(1) if m else full_text


    # 3) Clean out *all* stray preamble / abstract bits from that body
    body = remove_original_preamble(doc_body)

    # 4) Now split sections safely and convert
    sections = split_latex_by_sections(body)
    latex_body = process_sections_into_latex(sections, journal_name)

    # 5) Reassemble
    parts = []
    if title:
        parts.append(f"\\title{{{title}}}\n\\maketitle")
    if abstract:
        abstract = remove_code_block_markers(abstract)
        parts.append(abstract)
    parts.extend(latex_body)

    with open("survey_paper.tex","w",encoding="utf-8") as fo:
        fo.write("\n\n".join(parts))
    logger.info("✅ LaTeX document successfully written to survey_paper.tex")

 
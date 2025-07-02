import os
import re
import subprocess
import shutil
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

os.environ["MODEL"] = 'gpt-4.1'

llm = LLM(model="gpt-4.1", temperature=0)

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







import os
import re
import shutil
import subprocess
import time

def build_acm_pdf(tex_file: str, bib_file_path: str, output_dir: str = "./output", output_name: str = "final_paper"):
    os.makedirs(output_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    user_log_path = os.path.join(output_dir, f"{output_name}_{timestamp}.userlog")

    def log(msg: str):
        print(msg)
        with open(user_log_path, "a", encoding="utf-8") as logf:
            logf.write(msg + "\n")

    with open(tex_file, "r", encoding="utf-8") as f:
        tex_content = f.read()

    title_match = re.search(r'\\title\{(.+?)\}', tex_content, re.DOTALL)
    title = title_match.group(1).strip() if title_match else ""
    abstract_match = re.search(r'\\begin\{abstract\}(.+?)\\end\{abstract\}', tex_content, re.DOTALL)
    abstract = abstract_match.group(1).strip() if abstract_match else ""

    body = re.sub(r'\\title\{(.+?)\}', '', tex_content, flags=re.DOTALL)
    body = re.sub(r'\\begin\{abstract\}(.+?)\\end\{abstract\}', '', body, flags=re.DOTALL)
    body = re.sub(r'\\maketitle', '', body, flags=re.DOTALL)

    if "\\cite" not in tex_content:
        log("⚠️ No citation commands (e.g., \\cite{}) found in the .tex content.")

    if not os.path.exists(bib_file_path):
        log(f"❌ Bibliography file not found at: {bib_file_path}")
    else:
        with open(bib_file_path, "r", encoding="utf-8") as bibf:
            bib_content = bibf.read()
            if not bib_content.strip():
                log("❌ Your .bib file appears to be empty.")
            else:
                log("✅ .bib file loaded and non-empty.")

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
    tex_output_path = os.path.join(output_dir, f"{output_name}.tex")
    with open(tex_output_path, "w", encoding="utf-8") as f:
        f.write(final_tex)

    bib_output_path = os.path.join(output_dir, "references.bib")
    try:
        shutil.copyfile(bib_file_path, bib_output_path)
    except Exception as e:
        log(f"❌ Failed to copy bibliography file: {e}")

    compile_steps = [
        ["pdflatex", "-interaction=nonstopmode", f"{output_name}.tex"],
        ["bibtex", f"{output_name}"],
        ["pdflatex", "-interaction=nonstopmode", f"{output_name}.tex"],
        ["pdflatex", "-interaction=nonstopmode", f"{output_name}.tex"],
    ]

    try:
        for cmd in compile_steps:
            try:
                subprocess.run(cmd, cwd=output_dir, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if cmd[0] == "bibtex":
                    bbl_path = os.path.join(output_dir, f"{output_name}.bbl")
                    if os.path.exists(bbl_path):
                        log(f"📖 BibTeX .bbl generated successfully: {bbl_path}")
                        blg_path = os.path.join(output_dir, f"{output_name}.blg")
                        if os.path.exists(blg_path):
                            with open(blg_path, "r", encoding="utf-8") as f:
                                tail = "".join(f.readlines()[-10:])
                                log("📄 BibTeX log tail:\n" + tail)
                    else:
                        log("❌ BibTeX .bbl file was NOT generated. Check citations or .bib entries.")
            except subprocess.CalledProcessError:
                log(f"⚠️ Ignored non-fatal error at step: {' '.join(cmd)}")

        log(f"✅ ACM-style PDF generated at {os.path.join(output_dir, f'{output_name}.pdf')}")
        log(f"📝 Full user log saved to {user_log_path}")

    except Exception as e:
        log(f"❌ Full compilation failed: {e}")


        
        
def clean_bibliography(tex_path):
    with open(tex_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    cleaned_lines = []
    for line in lines:
        if line.strip().startswith(r"\bibliographystyle") or line.strip().startswith(r"\bibliography"):
            continue  # 🚫 skip these lines
        cleaned_lines.append(line)

    with open(tex_path, "w", encoding="utf-8") as f:
        f.writelines(cleaned_lines)

    print(f"✅ Removed \\bibliographystyle{{...}} and \\bibliography{{...}} from {tex_path}")

# Example usage
clean_bibliography("survey_paper.tex")

# ==== Example usage ====
if __name__ == "__main__":
    
    build_acm_pdf(
        tex_file="survey_paper.tex",
        bib_file_path="references.bib",
        output_dir="pdf_output",
        output_name="survey_paper"
    )

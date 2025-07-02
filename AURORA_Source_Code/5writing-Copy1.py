import os
from dotenv import load_dotenv
 
load_dotenv()  # This loads the variables from .env into os.environ

from crewai import LLM, Agent, Crew, Task
from crewai import Crew, Process, Agent, Task

#OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")



 
# ------------------------------
# Initialize Environment Variables
# ------------------------------
 

#OPENAI_MODEL_NAME = os.environ.get("OPENAI_MODEL_NAME", "gpt-4o")  # Using the 8K context model
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")


#os.environ["MODEL"] = 'gemini/gemini-2.5-pro-preview-03-25'
#llm = LLM(model="gemini/gemini-2.5-pro-preview-03-25", temperature=0)
os.environ["MODEL"] = 'gpt-4.1-mini'

llm = LLM(model="gpt-4.1-mini", temperature=0)

# Initialize the LLM (internally uses o3-mini for 4o-mini)
#llm = LLM(model="4o-mini", temperature=0)

import requests
import pandas as pd
import re
import asyncio
from typing import List

import re
# ✅ Function to read the outline file
def read_outline(file_path):
    """Reads the outline from a markdown file."""
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()
import re

def clean_outline_numbering(outline_text):
    """
    Cleans up redundant section numbering (e.g., "Section 7: 7.") and ensures sub-sections are nested properly.
    Also removes the trailing citations block if present.
    
    Parameters:
        outline_text (str): The raw outline text.
    
    Returns:
        str: The cleaned outline with properly formatted section numbers.
    """
    cleaned_lines = []
    previous_section = None
    in_citation_block = False

    for line in outline_text.splitlines():
        # Detect start of the citation block
        if re.match(r'^\s*[*-]*\s*\*{2}Citations.*\*{2}', line):
            in_citation_block = True
            continue  # Skip this line

        # Skip all lines that look like [1][2][3]...
        if in_citation_block:
            if re.match(r'^\s*(\[\d+\])+\s*$', line):
                continue
            else:
                in_citation_block = False  # End of citation block

        section_match = re.match(r'^\s*🔹\s+\*\*Section\s+(\d+):\s+\d+\.\s+(.*?)\*\*', line)
        subsection_match = re.match(r'^\s*###\s+(\d+\.\d+)\s+(.*)', line)

        if section_match:
            section_number = section_match.group(1)
            section_title = section_match.group(2)
            previous_section = section_number
            cleaned_lines.append(f"🔹 **Section {section_number}: {section_title}**")

        elif subsection_match and previous_section:
            subsection_number = subsection_match.group(1)
            subsection_title = subsection_match.group(2)
            cleaned_lines.append(f"### {previous_section}.{subsection_number.split('.')[1]} {subsection_title}")

        else:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


# ✅ Read and clean the outline file
file_path = "survey_paper_outline_one_by_one.md"
outline_text = read_outline(file_path)
cleaned_outline_text = clean_outline_numbering(outline_text)

# ✅ Save the cleaned outline for validation
with open("cleaned_survey_paper_outline.md", "w", encoding="utf-8") as f:
    f.write(cleaned_outline_text)

print("✅ Outline has been cleaned and saved as 'cleaned_survey_paper_outline.md'")


import re

# ✅ Function to read the outline file
def read_outline(file_path):
    """Reads the outline from a markdown file."""
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()

# ✅ Function to split the outline into structured sections and further break large sections into smaller parts
def split_outline_by_subsections(outline):
    """
    Splits the research paper outline into structured sections and ensures that each subsection (A, B, C, etc.) 
    remains separate while maintaining logical flow.

    Args:
        outline (str): The full outline text from the markdown file.

    Returns:
        list: List of structured subsections for processing.
    """
    sections = []
    current_section = {"title": None, "content": ""}
    current_subsection = None

    for line in outline.splitlines():
        # Remove leading markdown heading markers (e.g., '#' or '##')
        cleaned_line = re.sub(r'^#+\s*', '', line).strip()

        # ✅ Match main section headers (e.g., "1. Introduction" or "3. Range Search and Indexing Structures")
        section_match = re.match(r'^(\d+)\.\s\*\*(.*?)\*\*', cleaned_line) or re.match(r'^(\d+)\.\s+(.*)', cleaned_line)

        # ✅ Match subsection headers (e.g., "**A. Multidimensional Binary Search Trees (k-d trees)**")
        subsection_match = re.match(r'^\*\*(\w+)\.\s(.*?)\*\*', cleaned_line)

        if section_match:
            # ✅ Save the previous section before starting a new one
            if current_section["title"]:
                sections.append(current_section)

            # ✅ Start a new section
            current_section = {"title": f"{section_match.group(1)}. {section_match.group(2)}", "content": ""}
            current_subsection = None  # Reset subsection tracking

        elif subsection_match:
            # ✅ If a new subsection starts, save the previous one before continuing
            if current_subsection:
                sections.append(current_subsection)

            # ✅ Start a new subsection
            current_subsection = {
                "title": f"{current_section['title']} - {subsection_match.group(1)}. {subsection_match.group(2)}",
                "content": ""
            }

        else:
            # ✅ Append content to the current subsection if exists, otherwise to section
            if current_subsection:
                current_subsection["content"] += f"{cleaned_line}\n"
            else:
                current_section["content"] += f"{cleaned_line}\n"

    # ✅ Save the last remaining subsection or section
    if current_subsection:
        sections.append(current_subsection)
    elif current_section["title"]:
        sections.append(current_section)

    return sections

# ✅ File path of the outline
file_path = "cleaned_survey_paper_outline.md"

# ✅ Read and process the outline
outline_text = read_outline(file_path)
sections = split_outline_by_subsections(outline_text)

# ✅ Display structured sections
for i, section in enumerate(sections, start=1):
    print(f"🔹 **Section {i}: {section['title']}**\n")
    print(f"📄 **Content:**\n{section['content']}\n{'-'*60}")
import pandas as pd
import re

# ✅ Load the CSV file into a DataFrame
csv_file = "summaries_dedup.csv"  # Ensure the correct file path
info_df = pd.read_csv(csv_file)

# ✅ Ensure the required columns exist in the DataFrame
expected_columns = ['Summary', 'Index']
missing_columns = [col for col in expected_columns if col not in info_df.columns]

if missing_columns:
    raise ValueError(f"🚨 Missing columns in CSV: {missing_columns}")

# ✅ Define a function to remove citations and normalize spaces
def remove_citations(text):
    """Remove citations enclosed in square brackets and normalize spaces."""
    if isinstance(text, str):
        # Remove citations using regex (only square brackets with citations)
        cleaned_text = re.sub(r'\s*\[[^\]]+\]', '', text)
        # Normalize spaces and strip leading/trailing spaces
        return re.sub(r'\s+', ' ', cleaned_text.strip())
    return ''  # Return an empty string if the value is not a string

# ✅ Process the DataFrame and store results in a list of dictionaries
info_list = info_df[['Summary', 'Index']].dropna().assign(
    summary=lambda df: df['Summary'].apply(remove_citations),
    citation=lambda df: df['Index']
).to_dict(orient='records')

# ✅ Print the first 5 cleaned summaries for verification
for item in info_list[:5]:
    print(f"📌 Summary: {item['summary']}\n🔹 Citation: {item['citation']}\n{'-'*60}")
import re
import os

# Define the writer agent responsible for completing sections of the research paper
writer_agent = Agent(
    role="Senior Research Scientist",
    goal="Produce publication-quality paper sections with rigorous academic standards based on the outline, using provided summaries and citations.",
    verbose=False,
    model=llm,
    Memory=False,
    backstory="You are a post-doc level researcher with publications in top journals such as Nature and Cell. Recipient of NSF CAREER Award and multiple best paper prizes.Your expertise spans advanced AI applications in healthcare, pharmaceuticals, and scientific domains.",
    allow_delegation=False
)
editor_agent = Agent(
    role="Research Editor",
    goal="Refine and enhance research paper sections by improving clarity, coherence, citation consistency, and academic rigor.",
    verbose=False,
    model=llm,
    Memory=False,
    backstory=(
        "You are an experienced journal editor who has reviewed numerous top-tier research papers for leading scientific publications. "
        "Your expertise includes reorganizing content and presenting information in clear formats—including tables when beneficial "
        "for overviews, summaries, or numerical data comparisons."
    ),
    allow_delegation=False
)
def editor_agent_task():
    """
    Task for the editor agent to enhance clarity, coherence, structure, and academic rigor
    in the generated research paper section, while integrating LaTeX tables only where clearly justified.
    """

    return Task(
        description=(
            "### **Editorial Enhancement Task Overview**\n"
            "You are an academic research editor tasked with polishing a research paper section. Your goals are to:\n"
            "- Improve clarity, logical flow, and academic tone\n"
            "- Enhance sentence structure and transitions between paragraphs\n"
            "- Integrate **LaTeX tables** ONLY when they meaningfully improve comprehension\n\n"

            "### **Table Usage Rules:**\n"
            "✔ Use tables **very sparingly** — only for dense comparisons or structured data that benefits from grid-based layout.\n"
            "✔ All tables must use valid **LaTeX tabular format**, wrapped in a `table` environment.\n"
            "✔ Every table must include a **caption** and a **label** (e.g., `\\label{tab:method_comparison}`).\n"
            "✔ All table references in the narrative must use **LaTeX-style references** like `Table~\\ref{tab:method_comparison}`.\n"
            "✘ Do **not** insert tables for explanatory paragraphs, long descriptive sentences, or conceptual text.\n"
            "   - Instead, use well-formatted `\\begin{itemize} ... \\end{itemize}` bullet lists to improve readability.\n"
            "   - Tables should only be used to improve **visual clarity**, not for convenience or layout padding.\n"
            "✘ Do **not** use natural language like 'Table 1 shows...'; always use `Table~\\ref{...}`.\n"
            "✘ Do **not** duplicate content from the main paragraph into a table.\n"
            "✘ Do **not** modify or reinterpret citation usage.\n\n"

            "### **Expected Final Output:**\n"
            "A refined and publication-quality version of the research paper section with:\n"
            "- Fluent narrative structure and transitions\n"
            "- High academic rigor and improved clarity\n"
            "- Only essential LaTeX tables that improve comprehension\n"
            "- No tables that simply repeat or hold long narrative content\n"
            "- All tables referenced using `Table~\\ref{...}` syntax\n"
            "- Fully compliant academic formatting in LaTeX."
        ),
        expected_output=(
            "A polished academic section with enhanced clarity and structure, LaTeX tables only when truly beneficial, "
            "and all visual choices made for clarity and reader comprehension."
        ),
        agent=editor_agent,
        model=llm
    )






def writer_agent_task(outline_section, summary_info, citation_list):
    """
    Task definition for the writer agent to generate a research paper section with critical analysis,
    logical structure, and precise citation placement while ensuring conclusions are added only when necessary.
    
    Parameters:
        outline_section (str): The cleaned and properly formatted outline section.
        summary_info (str): Summaries of relevant research articles.
        citation_list (list): List of citation numbers to include in the writing.
    """
    
    # ✅ Ensure section numbering is formatted correctly before passing to the agent
    cleaned_outline_section = re.sub(r'Section\s+\d+:\s+', '', outline_section)  # Remove redundant "Section 7: 7."
    ref_citation_keys = [f"ref{int(c)}" for c in citation_list]
    return Task(
        description=(
            "### **Task Overview**\n"            
            "You are provided with a **structured research outline section**, relevant research summaries, and citation numbers. "
            "Your task is to write a **publication-quality section** that is **logically structured, critically engaging, and academically rigorous**.\n\n"

            "### **Provided Information**\n"
            f"🔹 **Outline Section (Cleaned):**\n{cleaned_outline_section}\n\n"
            f"🔹 **Summaries of Relevant Research:**\n{summary_info}\n\n"
            f"🔹 **Citations to Include:** {', '.join(ref_citation_keys)}\n\n"

            "### **Writing Strategy & Guidelines**\n"
            "1️⃣ **Develop a Coherent, Logical Argument**\n"
            "   - Do **not simply summarize** research; instead, **synthesize key findings** to develop a strong analytical narrative.\n"
            "   - Ensure **each paragraph builds upon the previous one**, forming a logically progressive discussion.\n\n"

            "2️⃣ **Demonstrate Critical Thinking**\n"
            "   - Evaluate existing research: **What are its strengths and weaknesses?**\n"
            "   - Compare findings from different sources, identifying trends, contradictions, and open challenges.\n"
            "   - Go beyond surface-level analysis to discuss **why certain approaches succeed or fail**.\n\n"

            "3️⃣ **Ensure Effective Citation Usage**\n"
            "   - Use **IEEE format** `[X]`, or LaTeX-style `\\cite{refX}`.\n"
            "   - Include only the citation keys provided above.\n"
            "   - **All citations must appear immediately after the sentence or claim they support.**\n"
            "   - Never list citations in bulk at the end of paragraphs.\n"
            "   - Use citations to support specific insights or claims, not as general placeholders.\n"
            "   - Group related references only when they support the same exact point.\n\n"

            "4️⃣ **Avoid Unnecessary Conclusions**\n"
            "   - **Only include conclusions in major sections** (e.g., a full chapter, a large review discussion, or the final section of a topic).\n"
            "   - **Do not add conclusions to purely methodological sections** or intermediate discussions.\n"
            "   - When writing a conclusion, ensure it **synthesizes insights rather than simply restating findings**.\n\n"

            "5️⃣ **Enhance Readability & Academic Precision**\n"
            "   - Use concise, precise academic language suited for a research audience.\n"
            "   - Ensure smooth transitions between ideas, maintaining a professional and logical flow.\n\n"

            "### **Expected Output**\n"
            "A **structured, critically engaging research paper section** that:\n"
            "✔ Builds a logically sound, high-level analytical argument.\n"
            "✔ Synthesizes multiple sources effectively instead of summarizing.\n"
            "✔ Uses **accurate and properly placed** citations.\n"
            "✔ **Avoids unnecessary conclusions** and redundant references.\n"
            "✔ Meets the academic standards for **publication in a top-tier journal**.\n\n"
            "✘ Do **not** include reference section.\n\n"
            "Ensure the final output is **clear, precise, and logically structured**."
        ),
        expected_output="A **highly analytical, well-structured** research paper section with strong insights, effective citations, and no unnecessary conclusions.",
        agent=writer_agent,
        model=llm,
        output_file=None  # Collect the output in code for further processing
    )

title_agent = Agent(
    role="Survey Title Composer",
    goal="Generate a concise, scoped title for a technical survey paper based on its outline.",
    model=llm,
    verbose=False,
    backstory="You write titles for academic survey papers based on their structure and themes."
)

abstract_agent = Agent(
    role="Survey Abstract Writer",
    goal="Generate a fluent, professional abstract summarizing the full research paper body.",
    model=llm,
    verbose=False,
    backstory="You write academic abstracts that summarize motivation, scope, contributions, and insights."
)
def title_task(outline_text):
    return Task(
        description=(
            "Generate a clear, specific, and scoped title for a  survey paper based on the following outline.\n"
            "Avoid generic phrases like 'An Overview of...' or 'A Review of...'. Make it scholarly and focused.\n\n"
            f"{outline_text}"
        ),
        expected_output="A well-formed academic paper title in latex such as \title{}.",
        agent=title_agent,
        model=llm
    )

def abstract_task(full_body):
    return Task(
        description=(
            "Write a concise academic abstract (under 200 words) summarizing the following full paper body.\n"
            "Include motivation, scope, key contributions, and conclusions. Use professional academic language.\n\n"
            f"{full_body}"
        ),
        expected_output="A fluent academic abstract for the paper.",
        agent=abstract_agent,
        model=llm
    )





import re
import sys

def complete_sections_with_agent(sections, info_list, outline_text=""):
    completed_sections = []

    for section in sections:
        section_title = section['title']
        section_content = section['content']
        
        # Detect citations like [4,5]
        citation_matches = re.findall(r'\[(\d+(?:, ?\d+)*)\]', section_content)
        citations = []
        for match in citation_matches:
            citations.extend(map(int, match.split(',')))

        related_summaries = [item['summary'] for item in info_list if int(item['citation']) in citations]
        full_citation_list = sorted(set(citations))

        task = writer_agent_task(
            outline_section=f"{section_title}\n{section_content}",
            summary_info="\n".join(related_summaries),
            citation_list=full_citation_list
        )
        editor_task = editor_agent_task()

        crew = Crew(
            agents=[writer_agent, editor_agent],
            tasks=[task, editor_task], 
            process=Process.sequential
        )
        result = crew.kickoff()
        completed_sections.append(result.output if hasattr(result, "output") else str(result))

    full_body = "\n\n".join(completed_sections)

    # === Title and Abstract ===
    title_text = "Title unavailable"
    if outline_text:
        title_result = Crew(
            agents=[title_agent],
            tasks=[title_task(outline_text)],
            process=Process.sequential
        ).kickoff()
        title_text = getattr(title_result, "output", str(title_result)).strip()

    abstract_result = Crew(
        agents=[abstract_agent],
        tasks=[abstract_task(full_body)],
        process=Process.sequential
    ).kickoff()
    abstract_text = getattr(abstract_result, "output", str(abstract_result)).strip()

    return f"# {title_text}\n\n## Abstract\n\n{abstract_text}\n\n{full_body}"


def convert_markdown_to_latex(md_text):
    # Title
    md_text = re.sub(r'^#\s+(.*)', r'\\title{\1}\n\\maketitle', md_text, flags=re.MULTILINE)

    # Abstract: capture only until the next ## header or end of file
    md_text = re.sub(
        r'^##\s+Abstract\s*\n(.*?)(?=^##\s|^\\section|\Z)',
        lambda m: '\\begin{abstract}\n' + m.group(1).strip() + '\n\\end{abstract}',
        md_text,
        flags=re.DOTALL | re.MULTILINE
    )


    # Sections
    md_text = re.sub(r'^##\s+(.*)', r'\\section{\1}', md_text, flags=re.MULTILINE)
    md_text = re.sub(r'^###\s+(.*)', r'\\subsection{\1}', md_text, flags=re.MULTILINE)

    # Citations [1, 2] → \cite{ref1, ref2}
    md_text = re.sub(r'\[(\d+(?:,\s*\d+)*)\]', lambda m: r'\\cite{' + ', '.join(f'ref{n.strip()}' for n in m.group(1).split(',')) + '}', md_text)

    # Bold text
    md_text = re.sub(r'\*\*(.*?)\*\*', r'\\textbf{\1}', md_text)

    # Bullet points
    md_text = re.sub(r'(?m)^-\s+(.+)', r'\\item \1', md_text)
    md_text = re.sub(r'(\\item .*(\n\\item .*)+)', r'\\begin{itemize}\n\1\n\\end{itemize}', md_text, flags=re.DOTALL)

    return (
        "\\documentclass[11pt]{article}\n"
        "\\usepackage{graphicx, hyperref, cite, booktabs, adjustbox}\n"
        "\\usepackage{amsmath, tabularx, xcolor, enumitem}\n"
        "\\usepackage{times}\n"
        "\\begin{document}\n\n"
        "\\author{Your Name}\n"
        "\\date{\\today}\n\n"
        + md_text +
        "\n\n\\bibliographystyle{unsrt}\n\\bibliography{references}\n"
        "\\end{document}"
    )

# === RUN PROCESS ===
completed_sections = complete_sections_with_agent(sections, info_list, outline_text)

# Save Markdown
md_file = 'completed_research_paper.md'
with open(md_file, "w", encoding="utf-8") as f:
    f.write(completed_sections)
print(f"📄 Markdown file saved: {md_file}")

# Convert to LaTeX
latex_text = convert_markdown_to_latex(completed_sections)

# Save LaTeX
tex_file = 'completed_research_paper.tex'
with open(tex_file, "w", encoding="utf-8") as f:
    f.write(latex_text)
print(f"📄 LaTeX file saved: {tex_file}")

print("✅ Research paper generation completed successfully!")


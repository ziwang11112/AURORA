import os
from dotenv import load_dotenv
 
load_dotenv()  # This loads the variables from .env into os.environ
import pandas as pd
import ast

from crewai import LLM, Agent, Crew, Task
from crewai import Crew, Process, Agent, Task
from crewai_tools import ScrapeWebsiteTool, SerperDevTool, FileReadTool
import csv

scrape_tool = ScrapeWebsiteTool()
search_tool = SerperDevTool()
file_read_tool = FileReadTool()

import ast
import re

def extract_python_list(text):
    # If there is a code block, extract its content
    code_block = re.search(r"```python(.*?)```", text, re.DOTALL)
    if code_block:
        code = code_block.group(1)
    else:
        # fallback: take everything that looks like a list
        list_match = re.search(r"\[.*\]", text, re.DOTALL)
        if list_match:
            code = list_match.group(0)
        else:
            raise ValueError("No Python list found in the input")
    # Remove leading/trailing whitespace or stray comments
    code = code.strip()
    # literal_eval should now work
    return ast.literal_eval(code)




OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")

print("OPENAI_API_KEY:", OPENAI_API_KEY)
print("SERPER_API_KEY:", SERPER_API_KEY)
os.environ["MODEL"] = 'gpt-4.1-mini'

llm = LLM(model="gpt-4.1-mini", temperature=0)
# Define the citation deduplication agent with clear instructions for removing duplicate citations.
deduplicated_agent = Agent(
    role="citation deduplicator",
    goal="Remove duplicate citations from a list while keeping one representative entry for each unique citation.",
    verbose=True,
    model=llm,
    tools=[search_tool,scrape_tool ],  # Document processing tools
    backstory=(
        "An expert agent specialized in deduplicating citation lists. The agent identifies duplicates based on "
        "the core citation content and removes redundant entries (even if there are slight differences in formatting, "
        "capitalization, or punctuation), ensuring that each unique citation appears only once. The output should be "
        "a list where each element is a string that begins with the original citation index followed by the citation text."
    ),
    allow_delegation=False,
    memory=False
)
validate_agent = Agent(
    role="Citation Deduplication Validator",
    goal="Double-check that all citation duplicates are removed, even if they differ in formatting.",
    verbose=True,
    model=llm,
    tools=[search_tool, scrape_tool],
    backstory=(
        "You are an expert in quality control of academic citation data. You examine deduplicated citation lists and validate "
        "whether any duplicates still remain, even if they differ slightly in punctuation, author order, or formatting. "
        "You produce a final clean list with all remaining duplicates removed."
    ),
    allow_delegation=False,
    memory=False
)
validated_agent_task=Task(
      description=(
            "Carefully validate the deduplicated_agent's work to ensure all duplicates have been removed. "
            "Duplicates may vary in formatting, punctuation, or slight text differences. If any remain, remove them. "
            "Return a Python list of fully deduplicated citation strings, without index numbers or metadata.\n\n"
            
        ),
        expected_output="only A final clean Python list of deduplicated citation strings with no duplicates remaining.",
        agent=validate_agent
 
    )

# Function to create a task that deduplicates the citation CSV.
def deduplicated_task(citation_list):
    return Task(
        description=(
            "Given the following citation list in CSV format, remove all duplicate citations so that only one instance "
            "of each unique citation remains. Remove entries that are duplicates even if they differ slightly in formatting. "
            "Ensure that the final output is a list of correct format of citation string do not include index. "
            "This list will later be saved as a CSV file named 'deduplicated_citations.csv'.\n\n"
            f"Citation List:\n{citation_list}"
        ),
        expected_output="Only A Python list of deduplicated citation strings with duplicates removed.",
        agent=deduplicated_agent,

    )

# === Load citations from results.csv ===
with open("results.csv", newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    citations = [row["Result"].strip() for row in reader if row["Result"].strip()]

# === Chunk into batches of N ===
def chunk_list(lst, chunk_size):
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i+chunk_size]

chunk_size = 100  # Adjust as needed
chunks = list(chunk_list(citations, chunk_size))

deduplicated_all = []

for i, chunk in enumerate(chunks):
    print(f"\n🔍 Running deduplication on chunk {i+1}/{len(chunks)} ({len(chunk)} citations)...")

    chunk_text = "\n".join(chunk)

    task = deduplicated_task(chunk_text)
    crew = Crew(
        agents=[deduplicated_agent, validate_agent],
        tasks=[task, validated_agent_task],
        process=Process.sequential
    )
    chunk_result = crew.kickoff()
    # Example usage:
    #parsed = extract_python_list(chunk_result)   # chunk_result is your LLM output
    print("debugginggg````````````````")
    print(type(chunk_result))
    print(chunk_result)

    # Extract output
    if hasattr(chunk_result, "raw"):
        chunk_result = chunk_result.raw

    try:
        parsed = ast.literal_eval(chunk_result)
        if isinstance(parsed, list):
            deduplicated_all.extend(parsed)
    except Exception as e:
        print(f"❌ Failed to parse chunk result: {e}")

# Final deduplication across all chunks
final_unique = list(dict.fromkeys(deduplicated_all))

# Save to CSV
df_final = pd.DataFrame(
    [{"Index": i, "Citation": c} for i, c in enumerate(final_unique, start=1)],
    columns=["Index", "Citation"]
)
df_final.to_csv("citation.csv", index=False, encoding="utf-8")
print(f"✅ Saved final deduplicated results to citation.csv with {len(final_unique)} entries.")

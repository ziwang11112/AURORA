import os
from dotenv import load_dotenv
import pandas as pd 
load_dotenv()
import glob

from crewai import LLM, Agent, Crew, Task, Process
import re
import warnings

warnings.filterwarnings('ignore')

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")

os.environ["MODEL"] = 'gpt-4.1-mini'

llm = LLM(model="gpt-4.1-mini", temperature=0)

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

topics_df = pd.read_csv('topics.csv')
topic_list = topics_df['topic'].tolist()
topic = "; ".join(topic_list)


def safe_extract_output(result):
    if isinstance(result, list):
        return [safe_extract_output(r) for r in result]
    return getattr(result, "output", str(result))


# Monkey-patch Crew.kickoff to auto-extract clean output
from crewai import Crew

original_kickoff = Crew.kickoff

def safe_kickoff(self, *args, **kwargs):
    result = original_kickoff(self, *args, **kwargs)
    return safe_extract_output(result)

Crew.kickoff = safe_kickoff


#!/usr/bin/env python3
import pandas as pd
import sys

def process_summaries(input_file, dedup_output_file, citation_output_file):
    

    try:
        df = pd.read_csv(input_file, encoding="utf-8")

        # ensure Summary is a string
        df["Summary"] = df["Summary"].fillna("").astype(str)

        # filter out missing‐summary rows (case‐insensitive)
        mask_missing = df["Summary"] \
            .str.strip() \
            .str.lower() \
            .str.contains("summary unavailable", na=False)

        df_filtered = df[~mask_missing]

        # drop duplicate citations
        df_dedup = df_filtered.drop_duplicates(subset=["Citation"]).copy()

        # reindex
        df_dedup["Index"] = range(1, len(df_dedup) + 1)

        # reorder columns
        cols = ["Index"] + [c for c in df_dedup.columns if c != "Index"]
        df_dedup = df_dedup[cols]

        # save full deduped CSV
        df_dedup.to_csv(dedup_output_file, index=False, encoding="utf-8")
        print(f"Deduplicated data saved to: {dedup_output_file}")
        print(f"Removed {len(df) - len(df_dedup)} rows (missing summary or dupes).")

        # save just Index + Citation
        df_cit = df_dedup[["Index", "Citation"]]
        df_cit.to_csv(citation_output_file, index=False, encoding="utf-8")
        print(f"Index & Citation saved to: {citation_output_file}")

    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)


    """ 
process_summaries(
        input_file="summaries.csv",
        dedup_output_file="summaries_dedup.csv",
        citation_output_file="citation.csv"
    )

""" 

import sys
import pandas as pd


import requests
import pandas as pd
import re
import asyncio
from typing import List

# Load the CSV file into a DataFrame
try:
    info_df = pd.read_csv('summaries_dedup.csv')
except FileNotFoundError:
    print("Error: The file 'summaries_dedup.csv' was not found.")
    exit()

# Initialize an empty list to store results
info_list = []

# Define a function to remove citations and normalize spaces
def remove_citations(text):
    if isinstance(text, str):
        cleaned_text = re.sub(r'\s*\[.*?\]\s*', '', text)  # Remove citations
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text.strip())  # Normalize spaces
        return cleaned_text
    return ''  # Return an empty string if not a string

# Ensure the column names exist in the DataFrame
if 'Summary' not in info_df.columns or 'Index' not in info_df.columns:
    print("Error: Missing required columns ('Summary' or 'Index') in CSV file.")
    exit()

# Process the DataFrame
for _, row in info_df.iterrows():
    clean_summary = remove_citations(row['Summary'])
    info_list.append({
        'summary': clean_summary,
        'citation': row['Index']
    })

# Define the structure agent
structure_agent = Agent(
    role="Research Paper Organizer",
    goal="Generate a professional outline for a survey paper based on provided summaries and citations.",
    verbose=False,
    model=llm,
    backstory="You specialize in analyzing research summaries and organizing them into coherent structures for survey papers.",
    allow_delegation=True
)

def structure_agent_task(batch_summaries_and_citations, topic):
    return Task(
        description=(
            f"Input: {batch_summaries_and_citations}\n"
            f"Analyze the provided batch of summaries and citation numbers to extract key themes related to {topic}. "
            "Group the summaries into thematic sections and generate a structured outline. "
            "Ensure that all citations are included and formatted using square brackets []. "
            "The language should be precise, well-structured, and aligned with the tone of a professional survey paper."
        ),
        expected_output="A structured outline including sections and subsections with corresponding citation numbers.",
        agent=structure_agent,
        human_input=False
    )

# Function to split data into batches
def split_into_batches(data_list, batch_size):
    for i in range(0, len(data_list), batch_size):
        yield data_list[i:i + batch_size]

# Get user input
#topic = " Advances in Hashing, Clustering, Deep Clustering, Entity Resolution, and Interpretable Techniques for Efficient Image, Cross-Modal Retrieval, and Large Vector Databases"
batch_size = 5
batches = list(split_into_batches(info_list, batch_size))

# Initialize an empty list to store partial outlines
partial_outlines = []

# Process each batch sequentially with retries
for batch_num, batch in enumerate(batches, start=1):
    retry_attempts = 3
    for attempt in range(retry_attempts):
        try:
            print(f"Processing batch {batch_num}, attempt {attempt + 1}")
            task = structure_agent_task(batch, topic)
            crew = Crew(agents=[structure_agent], tasks=[task], process=Process.sequential)
            result = crew.kickoff()
            
            if result:
                partial_outlines.append(result)
                print(f"Batch {batch_num} processed successfully.")
                break  # Exit retry loop if successful
        except Exception as e:
            print(f"Error processing batch {batch_num}, attempt {attempt + 1}: {e}")
            if attempt == retry_attempts - 1:
                print(f"Skipping batch {batch_num} after {retry_attempts} failed attempts.")

# Print all collected outlines
print("\nGenerated Survey Paper Outline Sections:")
for i, outline in enumerate(partial_outlines, start=1):
    print(f"\n--- Partial Outline {i} ---\n")
    print(outline)
with open('partial_outlines.md', 'w', encoding='utf-8') as f:
    for idx, partial in enumerate(partial_outlines, start=1):
        f.write(f"# Partial Outline {idx}\n\n{partial}\n\n")
        
        
        
merge_agent = Agent(
    role="outline merger",
    goal="Merge two outlines into a single outline, preserving all citations separately.",
    verbose=True,
    memory=True,
    model=llm,
    backstory="You excel at combining research outlines step-by-step while ensuring all citations remain intact.",
    allow_delegation=False
)

validate_agent = Agent(
    role="research outline validator",
    goal="Ensure all citations from the original outlines are present and formatted separately in the merged outline.",
    verbose=True,
    memory=True,
    model=llm,
    backstory="You ensure no citations are lost and are correctly formatted during the merging process.",
    allow_delegation=False
)

def extract_citations(text):
    return set(map(int, re.findall(r'\[(\d+)\]', text)))

def strip_references(outline):
    for marker in ['References\n', '**References**', '## References', '\nReferences\n']:
        if marker in outline:
            outline = outline.split(marker)[0]
    for marker in ['Abstract:', 'Title:', '# ', '\n\n---\n\n']:
        if marker in outline:
            outline = outline.split(marker, 1)[1] if marker in outline else outline
    return outline.strip()

def safe_output(result):
    return result.output if hasattr(result, "output") else str(result)

def merge_two_outlines(outline1, outline2, step):
    cleaned_outline1 = strip_references(outline1)
    cleaned_outline2 = strip_references(outline2)

    citations1 = extract_citations(cleaned_outline1)
    citations2 = extract_citations(cleaned_outline2)
    all_citations = citations1.union(citations2)

    task_description = f"""### **Task: Merge Step {step}**
🔹 Merge the following **two outlines** into a **single cohesive outline**.
🔹 **Preserve ALL citation numbers** from both outlines, ensuring none are lost.
🔹 Format citations **separately** in square brackets (e.g., [1][2][3], NOT [1, 2, 3]).
🔹 Group similar themes (e.g., Introduction, Range Search, Similarity Search, Clustering) without strict numbering yet.
🔹 Maintain logical flow and professional tone.
🔹 **Do NOT include a reference section**; only include citations within the outline.

### **Input Outlines:**
#### Outline 1:
{cleaned_outline1}

#### Outline 2:
{cleaned_outline2}

### **Expected Output:**
✅ A merged outline with all citations preserved and formatted separately."""

    merge_task = Task(description=task_description, expected_output="A merged outline with all citations preserved.", agent=merge_agent, model=llm)
    crew = Crew(agents=[merge_agent], tasks=[merge_task], process=Process.sequential)
    merged_result = crew.kickoff()

    merged_text = safe_output(merged_result)
    merged_citations = extract_citations(merged_text)
    missing_citations = all_citations - merged_citations
    if missing_citations:
        print(f"🚨 MISSING CITATIONS IN STEP {step}: {sorted(missing_citations)}. Validating...")
        merged_result = validate_missing_citations([cleaned_outline1, cleaned_outline2], merged_text, missing_citations)

    return safe_output(merged_result)

def validate_missing_citations(outlines, merged_outline, missing_citations):
    originals_block = "\n".join([f"#### Outline {i+1}:\n{outline}" for i, outline in enumerate(outlines)])

    task_description = f"""### **Task:**
🔹 Review the merged outline and insert the following missing citations where they logically fit: {sorted(missing_citations)}
🔹 Ensure all citations from the original outlines are included.
🔹 Format citations **separately** in square brackets (e.g., [1][2][3], NOT [1, 2, 3]).
🔹 Preserve the existing structure and professional tone.
🔹 **Do NOT include a reference section**.

### **Original Outlines:**
{originals_block}

### **Current Merged Outline:**
{merged_outline}

### **Expected Output:**
✅ A revised merged outline with all missing citations inserted, formatted separately."""

    validate_task = Task(description=task_description, expected_output="A validated merged outline with all citations preserved and formatted separately.", agent=validate_agent, model=llm)
    validate_crew = Crew(agents=[validate_agent], tasks=[validate_task], process=Process.sequential)
    validated_result = validate_crew.kickoff()

    return safe_output(validated_result)

def structure_final_outline(merged_outline):
    task_description = f"""### **Task: Final Outline Structuring**
🔹 Transform the following **merged outline** into a **well-structured survey paper outline**
🔹 **Preserve ALL citation numbers**, ensuring none are lost.
🔹 Format citations **separately** in square brackets (e.g., [1][2][3], NOT [1, 2, 3]).
🔹 Organize content into numbered sections and subsections based on thematic groupings
🔹 Ensure a logical flow and professional tone suitable for a survey paper.
🔹 **Do NOT include a reference section**; only include citations within the outline.

### **Merged Outline:**
{merged_outline}

### **Expected Output:**
✅ A single, structured outline with numbered sections and subsections, containing all citations formatted separately."""

    structure_task = Task(description=task_description, expected_output="A professionally structured final outline with all citations preserved.", agent=merge_agent, model=llm)
    crew = Crew(agents=[merge_agent], tasks=[structure_task], process=Process.sequential)
    final_result = crew.kickoff()

    return safe_output(final_result)

def insert_missing_citations_from_partial_outlines(final_outline, all_citations, partial_outlines):
    final_citations = extract_citations(final_outline)
    missing_citations = all_citations - final_citations

    if not missing_citations:
        return final_outline

    citation_context = {}
    for i, outline in enumerate(partial_outlines):
        for line in outline.splitlines():
            citations = extract_citations(line)
            for cit in citations:
                if cit in missing_citations and cit not in citation_context:
                    citation_context[cit] = f"From Outline {i+1}: {line.strip()}"

    context_block = "\n".join([f"- [{cit}]: {citation_context.get(cit, 'Context not found')}" for cit in sorted(missing_citations)])

    task_description = f"""### **Task: Insert Missing Citations from Partial Outlines**
🔹 Insert the following missing citations into the provided outline where they logically fit:
{context_block}
🔹 Deduce the subtopic for each citation based on its original context and provide a concise summary.
🔹 Format citations **separately** in square brackets (e.g., [1][2][3], NOT [1, 2, 3]).
🔹 Preserve the existing structure and professional tone.
🔹 **Do NOT include a reference section**; only include citations within the outline.

### **Current Outline:**
{final_outline}

### **Expected Output:**
✅ A revised outline with all missing citations inserted with summaries, formatted separately."""

    insert_task = Task(description=task_description, expected_output="A revised outline with all missing citations inserted with summaries.", agent=validate_agent, model=llm)
    crew = Crew(agents=[validate_agent], tasks=[insert_task], process=Process.sequential)
    revised_result = crew.kickoff()

    return safe_output(revised_result)

def merge_outlines_one_by_one(outlines):
    if not outlines:
        return ""

    current_merged = strip_references(outlines[0])
    for i, next_outline in enumerate(outlines[1:], start=1):
        print(f"Merging outline {i+1} into the current result...")
        current_merged = merge_two_outlines(current_merged, next_outline, i+1)

    final_outline = structure_final_outline(current_merged)

    all_citations = set().union(*[extract_citations(outline) for outline in outlines])
    final_outline = insert_missing_citations_from_partial_outlines(final_outline, all_citations, outlines)

    final_citations = extract_citations(final_outline)
    still_missing = all_citations - final_citations
    if still_missing:
        print(f"⚠️ FINAL PASS: Reinserting still-missing citations: {sorted(still_missing)}")
        final_outline = insert_missing_citations_from_partial_outlines(final_outline, all_citations, outlines)

    return final_outline.strip()



final_merged_outline = merge_outlines_one_by_one(partial_outlines)

with open('survey_paper_outline_one_by_one.md', 'w', encoding='utf-8') as f:
    f.write("# Survey Paper Outline\n\n")
    f.write(final_merged_outline)

print("✅ Survey paper outline saved to 'survey_paper_outline_one_by_one.md'")
print("\n✅ FINAL MERGED OUTLINE PREVIEW (first few lines):\n")
print("\n".join(final_merged_outline.splitlines()[:10]))

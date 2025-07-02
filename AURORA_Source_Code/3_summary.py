#!/usr/bin/env python3
 
 
import os
from dotenv import load_dotenv
 
load_dotenv() 
import warnings
warnings.filterwarnings('ignore')

import pandas as pd
from crewai import Agent, Crew, Process, Task,LLM
from langchain.tools import tool
import re
from crewai.tools import BaseTool
 
import requests
import csv
import hashlib
import logging

import time
import random
import threading
import unicodedata
import sys
import pandas as pd
 
from PyPDF2 import PdfReader
import requests
import csv
import hashlib
import logging
import sys
import time
import random
import threading
import unicodedata
 
import json

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Load API keys
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")

print("OPENAI_API_KEY:", OPENAI_API_KEY)
print("SERPER_API_KEY:", SERPER_API_KEY)
os.environ["MODEL"] = 'gpt-4.1-mini'

llm = LLM(model="gpt-4.1-mini", temperature=0)

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
#from crewai_tools import SeleniumScrapingTool
#scrape_tool = SeleniumScrapingTool()

#############################
# 1. PDF Readertool Definition
#############################
class PDFReadertool(BaseTool):
    name: str = "pdf_reader"
    description: str = "Read the content of a PDF from a URL and return the extracted text."

    def _run(self, pdf_url: str, page_limit: int = 5):
        """Downloads and reads the first few pages of a PDF."""
        try:
            response = requests.get(pdf_url)
            response.raise_for_status()
            temp_pdf_path = "/tmp/temp_paper.pdf"
            with open(temp_pdf_path, "wb") as f:
                f.write(response.content)
            reader = PdfReader(temp_pdf_path)
            text = ""
            max_pages = min(len(reader.pages), page_limit)
            for i in range(max_pages):
                page_text = reader.pages[i].extract_text()
                if page_text:
                    text += page_text + "\n\n"
            os.remove(temp_pdf_path)
            return text if text else "No readable text found in PDF."
        except Exception as e:
            return f"Error reading PDF: {e}"

pdf_reader_tool = PDFReadertool()
# Define the safe extraction logic
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

#############################
# 2. Utility Functions
#############################
def truncate_text(text, max_chars=4000):
    return text[:max_chars] if len(text) > max_chars else text

def clean_text(text):
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    return text

def read_csv(filename):
    try:
        with open(filename, "r", encoding="utf-8", errors="replace") as file:
            return [row for row in csv.DictReader(file) if "Index" in row and "Citation" in row]
    except FileNotFoundError:
        logging.error(f"File '{filename}' not found.")
        return []
    except Exception as e:
        logging.error(f"Error reading '{filename}': {e}")
        return []

def extract_link(citation):
    match = re.search(r'(https?://\S+)', citation)
    return match.group(1).rstrip(').,') if match else None
 


# --- Clean up old outputs before running ---
for fname in ["summaries.csv", "errors.csv", "summaries_dedup.csv"]:
    if os.path.exists(fname):
        os.remove(fname)
        print(f"Removed old file: {fname}")

# … the rest of your imports and code follow …


#############################
search_agent = Agent(
    role="Academic Content Retriever",
    goal="Collect the key textual content from an academic paper, including abstract, introduction, and if available, full text sections via HTML scraping or preview.",
    verbose=True,
    model=llm,
    tools=[search_tool, scrape_tool],  # pdf_reader_tool removed
    backstory=(
        "When given a citation and optional link, attempt to scrape the HTML version of the paper page. "
        "extract the abstract, introduction, methods, results, discussion, and conclusion. "
        "If only partial content is available, extract the partial content. "
        "Always structure the output in JSON with fields: abstract, introduction, methods, results, discussion, conclusion, and so on."
    ),
    allow_delegation=True,
    max_rpm=450000
)


def search_task(link, citation):
    return Task(
        description=(         
            f"1. If the direct link `{link}` is provided, attempt to retrieve structured content from the paper.\n"
            f"2. **If the direct link fails**, search using the authors and title from citation: `{citation}`:\n" 
            f"   - If full text is accessible, extract all of: abstract, introduction, methods, results, discussion, challenge, future work and conclusion.\n"
            f"   - If only partial content is visible, extract just partial content.\n"
            f"3. Return a JSON object with the fields:\n"
            f"   - `abstract`, `introduction`, `methods`, `results`, `discussion`, `challenges`, `future_work`, `conclusion`, and other fields)."
           ),
        expected_output="A structured JSON object with extracted paper content.",
        agent=search_agent,
        model=llm,
        human_input=False
    )


#############################
# 4. Summary Agent (conditional)
#############################
 
summary_agent = Agent(
    role="Paper Keypoint Summarizer",
    goal="Write a one-paragraph summary of an academic paper using extracted fields (abstract, intro, etc.), with LaTeX formatting for equations or tables if relevant.",
    verbose=True,
    model=llm,
    tools=[],
    backstory=(
        "From search agent's output which is JSON object with keys: abstract, introduction, methods, results, discussion, conclusion, and others. "
        "summarize the paper.. "
        "If only abstract and introduction are available, summarize those instead. "
        "Embed critical equations using `$...$` or `$$...$$`, and format compact tables inline using LaTeX tabular syntax. "
        "If all fields are missing or empty, return exactly:\n"
        "`Summary unavailable due to missing data`"
    ),
    allow_delegation=True,
    max_rpm=450000,
    max_execution_time=60,
    memory=False
)


def summary_task():
    return Task(
        description=(
            "summarize the paper base on search agent's output which is JSON object with fields: abstract, introduction, methods, results, discussion, conclusion, and available (either 'full' or 'partial').\n\n"
            "• Use inline LaTeX for important equations (`$...$`) or small tables (with `tabular`).\n"
            "• If both abstract and introduction are missing or empty, return:\n"
            "`Summary unavailable due to missing data`\n\n"
            "Return only the paragraph. Do not include headings or extra commentary."
        ),
        expected_output="A concise summary  with optional LaTeX inline formatting.",
        agent=summary_agent,
        model=llm,
        human_input=False
    )





#############################
# 5. Error & Summary Processing Functions
#############################
def save_error_papers(error_papers, filename="errors.csv"):
    """Saves failed papers for retrying later, avoiding duplicate entries."""
    # Load existing errors (if any)
    existing = set()
    if os.path.isfile(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    existing.add((row["Index"], row["Citation"]))
        except Exception as e:
            logging.error(f"Error reading existing errors from {filename}: {e}")

    # Filter out duplicates
    new_errors = [ep for ep in error_papers if (ep["Index"], ep["Citation"]) not in existing]
    
    if not new_errors:
        return

    file_exists = os.path.isfile(filename)
    with open(filename, "a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["Index", "Citation"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(new_errors)
    logging.info(f"⚠️ Saved {len(new_errors)} new failed indices to {filename}.")

def summarize_papers(papers, max_retries=5, summary_filename="summaries.csv", error_filename="errors.csv"):
    """Processes a list of papers, generates summaries, saves them, and logs errors."""
    existing_hashes = set()
    existing_entries = set()
    if os.path.exists(summary_filename):
        with open(summary_filename, "r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            existing_hashes = {hashlib.md5((row.get("Summary", "") + row["Index"]).encode()).hexdigest() for row in reader}
            existing_entries = {(row["Index"], row["Citation"]) for row in reader}
    file_exists = os.path.isfile(summary_filename)
    try:
        with open(summary_filename, "a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=["Index", "Citation", "Summary"])
            if not file_exists:
                writer.writeheader()
            for paper in papers:
                index, citation = paper.get("Index", "").strip(), paper.get("Citation", "").strip()
                if not index or not citation:
                    logging.warning(f"⚠️ Skipping entry: Missing Index or Citation.")
                    continue
                if (index, citation) in existing_entries:
                    logging.warning(f"⚠️ Duplicate Index {index} & Citation already saved. Skipping.")
                    continue
                logging.info(f"📄 Processing Index {index}...")
                try:
                    link = extract_link(citation) or "None"
                    searching_task_obj, summarizing_task_obj = search_task(link, citation), summary_task()
                    for attempt in range(max_retries):
                        try:
                            crew = Crew(
                                agents=[search_agent, summary_agent],
                                tasks=[searching_task_obj, summarizing_task_obj],
                                process=Process.sequential
                            )
                            result = crew.kickoff()
                            if not result or result.strip() == "":
                                logging.warning(f"⚠️ Empty summary for Index {index}, skipping save.")
                                continue
                            result_str = json.dumps(result) if isinstance(result, dict) else str(result)
                            result = truncate_text(clean_text(result_str), max_chars=4000)
                            break  
                        except Exception as e:
                            wait_time = min(5 * (2 ** attempt), 60)
                            logging.error(f"⏳ Retrying Index {index} in {wait_time:.2f}s... Error: {e}")
                            time.sleep(wait_time)
                    else:
                        logging.error(f"❌ Final failure at Index {index}. Saving for retry.")
                        save_error_papers([{"Index": index, "Citation": citation}], filename=error_filename)
                        continue  
                    result_hash = hashlib.md5((result_str + str(index)).encode()).hexdigest()
                    if result_hash in existing_hashes:
                        logging.warning(f"⚠️ Duplicate detected for Index {index}, skipping save.")
                        continue
                    existing_hashes.add(result_hash)
                    existing_entries.add((index, citation))
                    writer.writerow({"Index": index, "Citation": citation, "Summary": result})
                    logging.info(f"✅ Summary saved for Index {index}.")
                except Exception as e:
                    logging.error(f"⚠️ Unexpected error at Index {index}: {e}")
                    save_error_papers([{"Index": index, "Citation": citation}], filename=error_filename)
    except PermissionError as pe:
        logging.error(f"❌ Cannot write to {summary_filename}. File might be locked. Error: {pe}")
    return




if __name__ == "__main__":
    log_file = "summary_log.txt"
    with open(log_file, "w", encoding="utf-8") as log_output:
        sys.stdout = log_output  # Redirect output to log file

        filename = "citation.csv"
        all_papers = read_csv(filename)
        
        # ✅ Corrected function call
        error_papers = summarize_papers(all_papers, summary_filename="summaries.csv", error_filename="errors.csv")

        sys.stdout.flush()  # Ensure everything is written before restoring output
        sys.stdout = sys.__stdout__  # Restore standard output
    
    print(f"Process completed. Check the log file: {log_file}")

 
import csv
import os

SUMMARY_FILE = "summaries.csv"
ERROR_FILE = "errors.csv"
TEMP_FILE = "temp_summaries.csv"  # Temporary file to store cleaned data
INVALID_KEYWORD = "summary unavailable"  # Keyword to identify invalid summaries

def process_summaries():
    """Removes invalid summaries and moves their Index & Citation to errors.csv"""

    if not os.path.exists(SUMMARY_FILE):
        print(f"❌ Error: {SUMMARY_FILE} not found.")
        return

    removed_entries = []
    file_exists = os.path.isfile(ERROR_FILE)

    try:
        with open(SUMMARY_FILE, "r", encoding="utf-8") as infile, \
             open(TEMP_FILE, "w", newline="", encoding="utf-8") as outfile:

            reader = csv.DictReader(infile)

            # Validate the required columns
            required_fields = {"Index", "Citation", "Summary"}
            if not required_fields.issubset(reader.fieldnames):
                print(f"❌ Error: Missing required columns in {SUMMARY_FILE}")
                return

            writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
            writer.writeheader()

            for row in reader:
                summary_text = row["Summary"].strip().lower()
                if INVALID_KEYWORD in summary_text:
                    removed_entries.append({"Index": row["Index"], "Citation": row["Citation"]})
                else:
                    writer.writerow(row)

        # Move removed rows to errors.csv
        if removed_entries:
            with open(ERROR_FILE, "a", newline="", encoding="utf-8") as errfile:
                writer = csv.DictWriter(errfile, fieldnames=["Index", "Citation"])
                if not file_exists:
                    writer.writeheader()
                writer.writerows(removed_entries)

        # Replace old summaries.csv with cleaned version
        os.replace(TEMP_FILE, SUMMARY_FILE)

        print(f"✅ Process completed: Moved {len(removed_entries)} invalid entries to {ERROR_FILE}")

    except Exception as e:
        print(f"❌ Error while processing: {e}")


if __name__ == "__main__":
    process_summaries()


import csv
import hashlib
import logging
import os
import json
import sys
import time

# ✅ Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)


def read_csv(filename):
    """Reads a CSV file and returns a list of dictionaries."""
    if not os.path.exists(filename):
        logging.warning(f"⚠️ File '{filename}' not found. Skipping.")
        return []
    
    with open(filename, "r", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def save_error_papers(error_papers, filename="errors.csv"):
    """Saves failed papers for retrying later."""
    if not error_papers:
        return  # No errors, nothing to save
    
    file_exists = os.path.isfile(filename)

    with open(filename, "a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["Index", "Citation"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(error_papers)

    logging.info(f"⚠️ Saved {len(error_papers)} failed indices to {filename}.")


def summarize_papers(papers, max_retries=5, summary_filename="summaries.csv", error_filename="errors.csv"):
    """Processes a list of papers, generates summaries, saves them, and logs errors."""
    existing_hashes = set()
    existing_entries = set()

    # ✅ Load existing summaries
    if os.path.exists(summary_filename):
        with open(summary_filename, "r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            existing_hashes = {hashlib.md5((row.get("Summary", "") + row["Index"]).encode()).hexdigest() for row in reader}
            existing_entries = {(row["Index"], row["Citation"]) for row in reader}

    file_exists = os.path.isfile(summary_filename)

    try:
        with open(summary_filename, "a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=["Index", "Citation", "Summary"])
            if not file_exists:
                writer.writeheader()

            for paper in papers:
                index, citation = paper.get("Index", "").strip(), paper.get("Citation", "").strip()
                if not index or not citation:
                    logging.warning(f"⚠️ Skipping entry: Missing Index or Citation.")
                    continue

                if (index, citation) in existing_entries:
                    logging.warning(f"⚠️ Duplicate Index {index} & Citation already saved. Skipping.")
                    continue

                logging.info(f"📄 Processing Index {index}...")

                try:
                    link = extract_link(citation) or "None"
                    searching_task, summarizing_task = search_task(link, citation), summary_task()

                    for attempt in range(max_retries):
                        try:
                            crew = Crew(
                                agents=[search_agent, summary_agent],
                                tasks=[searching_task, summarizing_task],
                                process=Process.sequential
                            )
                            result = crew.kickoff()

                            if not result or result.strip() == "":
                                logging.warning(f"⚠️ Empty summary for Index {index}, skipping save.")
                                continue

                            # Convert JSON result to string if needed
                            result_str = json.dumps(result) if isinstance(result, dict) else str(result)
                            result = truncate_text(clean_text(result_str), max_chars=4000)
                            break  
                        except Exception as e:
                            wait_time = min(5 * (2 ** attempt), 60)
                            logging.error(f"⏳ Retrying Index {index} in {wait_time:.2f}s... Error: {e}")
                            time.sleep(wait_time)
                    else:
                        logging.error(f"❌ Final failure at Index {index}. Saving for retry.")
                        save_error_papers([{"Index": index, "Citation": citation}], filename=error_filename)
                        continue  

                    result_hash = hashlib.md5((result_str + str(index)).encode()).hexdigest()

                    if result_hash in existing_hashes:
                        logging.warning(f"⚠️ Duplicate detected for Index {index}, skipping save.")
                        continue

                    existing_hashes.add(result_hash)  # ✅ Add before writing
                    existing_entries.add((index, citation))
                    writer.writerow({"Index": index, "Citation": citation, "Summary": result})
                    logging.info(f"✅ Summary saved for Index {index}.")

                except Exception as e:
                    logging.error(f"⚠️ Unexpected error at Index {index}: {e}")
                    save_error_papers([{"Index": index, "Citation": citation}], filename=error_filename)

    except PermissionError as pe:
        logging.error(f"❌ Cannot write to {summary_filename}. File might be locked. Error: {pe}")


def reindex_summaries(filename="summaries.csv"):
    """Reindexes summaries from 1 and saves back to the same file."""
    papers = read_csv(filename)
    
    if not papers:
        logging.warning(f"⚠️ No summaries found in {filename}. Skipping reindexing.")
        return

    # ✅ Assign new indices starting from 1
    for i, paper in enumerate(papers, start=1):
        paper["Index"] = str(i)

    with open(filename, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["Index", "Citation", "Summary"])
        writer.writeheader()
        writer.writerows(papers)

    logging.info(f"✅ Reindexed {len(papers)} summaries in {filename}.")


def process_error_papers():
    """Retries processing of failed papers in errors.csv and reindexes summaries."""
    error_filename = "errors.csv"
    summary_filename = "summaries.csv"

    # ✅ Read errors.csv (failed attempts)
    failed_papers = read_csv(error_filename)

    if not failed_papers:
        logging.info(f"🎉 No failed papers found in {error_filename}. Skipping retry.")
        return

    logging.info(f"🔄 Retrying {len(failed_papers)} failed papers from {error_filename}...")

    summarize_papers(failed_papers, summary_filename=summary_filename)

    # ✅ Reindex summaries
    reindex_summaries(summary_filename)

    # ✅ Remove `errors.csv` if all issues are fixed
    if not read_csv(error_filename):
        os.remove(error_filename)
        logging.info(f"🎉 All failed papers processed. Deleted {error_filename}.")

        
# ✅ MAIN EXECUTION
if __name__ == "__main__":
    logging.info("🚀 Starting error paper processing & reindexing...")
    process_error_papers()
    logging.info("✅ Process complete.")

 

#!/usr/bin/env python3
import pandas as pd
import sys

def process_summaries1(input_file, dedup_output_file, citation_output_file):
    

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



process_summaries1(
        input_file="summaries.csv",
        dedup_output_file="summaries_dedup.csv",
        citation_output_file="citation.csv"
    )

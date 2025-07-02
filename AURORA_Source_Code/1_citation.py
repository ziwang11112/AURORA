#!/usr/bin/env python3
import os
import sys
import json
import csv
import re
from dotenv import load_dotenv
from crewai import LLM, Agent, Crew, Task, Process
from crewai_tools import SerperDevTool, ScrapeWebsiteTool

# —————— Load environment ——————
load_dotenv()

GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY")
SERPER_API_KEY  = os.getenv("SERPER_API_KEY")
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY")
#os.environ["MODEL"] = "gpt-4.1"
os.environ["MODEL"] = "gpt-4.1-mini"

# Initialize LLM
llm = LLM(model="gpt-4.1-mini", temperature=0, max_tokens=8192, truncate=True)

search_tool = SerperDevTool(api_key=SERPER_API_KEY)
scrape_tool = ScrapeWebsiteTool()

# —————— Monkey-patch Crew for clean output ——————
from crewai import Crew
_orig_kickoff = Crew.kickoff
def _patched_kickoff(self, *args, **kwargs):
    result = _orig_kickoff(self, *args, **kwargs)
    return getattr(result, "output", str(result))
Crew.kickoff = _patched_kickoff

# —————— Load Topics ——————
topics_csv = os.path.join(os.getcwd(), "topics.csv")
topics = []
with open(topics_csv, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        topic = row.get("topic", "").strip()
        if topic:
            topics.append(topic)
if not topics:
    print("No topics found in topics.csv.")
    sys.exit(1)

print("Parsed topics:", topics)


import time

def call_with_retry(crew, retries=3):
    for i in range(retries):
        try:
            return crew.kickoff()
        except Exception as e:
            if "RateLimitError" in str(e) or "429" in str(e):
                wait = 2 ** i
                print(f"⚠️ Rate limited, retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise e
    raise RuntimeError("Too many retries failed.")

 

# —————— Journal Recommendation Agent ——————
journal_search_agent = Agent(
    role="Journal Recommendation Specialist",
    goal="Identify reputable journals suitable for the given research topic.",
    verbose=False,
    model=llm,
    tools=[search_tool, scrape_tool],
    backstory=(
        "You are an expert in academic publishing and literature review. Your role is to identify high-quality, "
        "peer-reviewed journals with strong reputations, high impact factor and h-index scores."
        "You provide only the journal names in a clean format suitable for programmatic use."
    ),
    allow_delegation=False,
    memory=False
)

# Define the task to retrieve topic-specific journal names as an array
def find_suitable_journals_task(topic):
    """
    Task for the agent to find high-quality, topic-relevant journal names for a given research topic.

    Args:
        topic (str): The research topic to find suitable journals for.

    Returns:
        Task: A task that retrieves only highly relevant journal names and stores them in an array.
    """
    return Task(
        description=(
            f"Search for 3-5 highly relevant, high-impact, reputable journals related to the topic: '{topic}'. "
            "Prioritize major journals regardless of access type, focusing on quality and reputation. "
            "In addition, find at least one fully open-access journal and one preprint server (e.g., arXiv, bioRxiv, TechRxiv) if they contain substantial research on the topic. "
            "Use trusted academic databases like Google Scholar, JSTOR, or IEEE Xplore. "
            "Return only journal names in a structured array format without any extra metadata."
        ),
        expected_output=(
            "An array containing 3-5 journal or repository names highly relevant to the given topic. "
            "The list must include 3-5 major high-quality journals (regardless of access type), at least one fully open-access journal, and one preprint server if applicable. "
            "Journals must be strictly topic-focused. "
            #"Exclude hybrid journals where substantial content is behind a paywall unless no better option is available."
        ),
        agent=journal_search_agent,
        model=llm,
        human_input=False
    )


topic_journal_map = {}
for topic in topics:
    task = find_suitable_journals_task(topic)
    # Define the crew and execute the task
    crew = Crew(
            agents=[journal_search_agent],
            tasks=[task],
            process=Process.sequential
        )

    raw = call_with_retry(crew)
    time.sleep(3)  # throttle between journal searches

    try:
        journals = json.loads(raw)
    except Exception:
        journals = [raw] if isinstance(raw, str) else raw
    topic_journal_map[topic] = journals

print("Per-topic journals:")
for t, js in topic_journal_map.items():
    print(f"  • {t}: {js}")

 
 
 
 
 
 
import hashlib
import csv
research_paper_count = int(os.getenv("PAPER_COUNT"))
# Define the web search agent with a specific role and goal
web_search_agent = Agent(
    role="High-Quality Research Paper Finder",
    goal="Locate high-quality research papers from reputable journals with a high h-index related to a specific topic.",
    verbose=False,
    model=llm,
    tools=[search_tool,scrape_tool],
    backstory=(
        "As a Research Specialist, your role is to identify credible and authoritative journal articles. "
        "You use online tools and databases to locate papers from provided journals. "
        "Your output provides well-formatted citations ready for academic use."
    ),
    allow_delegation=False,
    memory=False
)

# Define a function to generate a unique hash for a paper
def generate_hash(title, authors, journal):
    """
    Generates a hash for a paper using its title, authors, and journal.
    """
    data = title + authors + journal
    return hashlib.md5(data.encode()).hexdigest()

# Define the task to find high-quality research papers
import hashlib
import csv
import re
import logging
import time
from crewai import Crew, Process
def setup_logging(log_filename="find_paper_log.txt"):
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), log_filename)
    logging.basicConfig(filename=log_path, level=logging.INFO, format="%(asctime)s - %(message)s")
    sys.stdout = open(log_path, "w", encoding="utf-8")

def find_high_quality_papers_task(batch_size, topic, source):
    return Task(
        description=(
            f"Search for {batch_size} recent (published in the last 8 years) high-quality, peer-reviewed research papers "
            f"highly related to the topic '{topic}' from the source '{source}'. Use reputable academic databases or open-access journals "
            "if necessary. For each paper, extract and format the citation in IEEE style (or another journal-specific style if applicable) "
            "that includes the following details:\n"
            "- Complete list of authors\n"
            "- Title of the paper\n"
            "- Publication venue (conference or journal name)\n"
            "- Volume and issue (if available), along with page numbers\n"
            "- Publication year\n"
            "- Direct URL to access the paper"
        ),
        expected_output="A list of formatted citations including authors, title, venue, volume/issue (if applicable), publication year, and URL.",
        agent=web_search_agent,
        model=llm
    )

def save_to_csv(data, filename="results.csv"):
    if not data: 
        print("No data to save.")
        return
    try:
        with open(filename, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["Index", "Result"])
            for idx, entry in enumerate(data, start=1):
                writer.writerow([idx, entry])
        print(f"Results saved to '{filename}'.")
    except Exception as e:
        print(f"Error while saving to CSV: {e}")

def collect_and_save_all_papers(topic_journal_map, paper_count=10):
    all_results = []
    seen_hashes = set()

    for topic, journals in topic_journal_map.items():
        if not journals:
            print(f"[SKIP] No journals found for topic: {topic}")
            continue
        print(f"\n🔍 Topic: '{topic}' — Journals: {journals}")

        for journal in journals:
            time.sleep(5)  # Delay to avoid rate limiting
            try:
                batch_size = min(paper_count, 3)
                task = find_high_quality_papers_task(batch_size, topic, journal)
                crew = Crew(
                    agents=[web_search_agent],
                    tasks=[task],
                    process=Process.sequential
                )
                raw = call_with_retry(crew)
                    

                # Flexible parsing
                if isinstance(raw, str):
                    entries = re.split(r"\n\d+[.)]|\n•", raw)
                elif isinstance(raw, list):
                    entries = raw
                else:
                    entries = [str(raw)]

                for entry in entries:
                    cleaned = entry.strip()
                    if cleaned:
                        h = hashlib.md5(cleaned.encode()).hexdigest()
                        if h not in seen_hashes:
                            seen_hashes.add(h)
                            all_results.append(cleaned)

            except Exception as e:
                print(f"[ERROR] fetching from {journal} for '{topic}': {e}")
                continue

    save_to_csv(all_results)

if __name__ == "__main__":
    log_file = "find_paper_log.txt"
    setup_logging(log_file)

    # Phase 1: Build topic_journal_map
    topic_journal_map = {}
    for topic in topics:
        task = find_suitable_journals_task(topic)
        crew = Crew(
            agents=[journal_search_agent],
            tasks=[task],
            process=Process.sequential
        )
        raw = call_with_retry(crew)
        time.sleep(3)  # throttle between journal searches

        try:
            journals = json.loads(raw)
        except Exception:
            journals = [raw] if isinstance(raw, str) else raw
        topic_journal_map[topic] = journals

    print("Per-topic journals:")
    for t, js in topic_journal_map.items():
        print(f"  • {t}: {js}")

    # Phase 2: Paper retrieval
    collect_and_save_all_papers(topic_journal_map, paper_count=research_paper_count)

    sys.stdout.flush()
    sys.stdout.close()
    sys.stdout = sys.__stdout__

#!/usr/bin/env python3
import os
import uuid
import json
import csv
from datetime import datetime
from dotenv import load_dotenv
import warnings

from crewai import LLM, Agent, Crew, Task, Process
from crewai_tools import ScrapeWebsiteTool, SerperDevTool

# —————— Static config ——————
load_dotenv()  # loads your API keys,MODEL,TEMPERATURE from .env

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL          = os.getenv("MODEL", "gpt-4.1-mini")
#MODEL          = os.getenv("MODEL", "gpt-4.1")
TEMPERATURE    = float(os.getenv("TEMPERATURE", 0.7))

warnings.filterwarnings("ignore")

# —————— Helpers for clean Crew output ——————
def safe_extract_output(result):
    if isinstance(result, list):
        return [safe_extract_output(r) for r in result]
    return getattr(result, "output", str(result))

from crewai import Crew
_original_kickoff = Crew.kickoff
def _patched_kickoff(self, *args, **kwargs):
    res = _original_kickoff(self, *args, **kwargs)
    return safe_extract_output(res)
Crew.kickoff = _patched_kickoff

# —————— Initialize LLM & tools ——————
llm         = LLM(model=MODEL, temperature=TEMPERATURE)
search_tool = SerperDevTool(api_key=SERPER_API_KEY)
scrape_tool = ScrapeWebsiteTool()

# —————— Step 1: generate run_id & output folder ——————
 

# —————— Step 2: prompt user for survey topic ——————
user_topic = input("Enter the topic for the survey paper: ").strip()

# —————— Step 3: define agent & task to refine keywords ——————
topic_identify_agent = Agent(
    role="Topic Identification Agent",
    goal="Extract precise and effective keywords from the user's research topic.",
    verbose=False,
    model=llm,
    tools=[],
    backstory=(
        "You are an expert in academic publishing and scholarly research. "
        "You specialize in identifying key terms and concepts from user-provided research topics."
    ),
    human_input=True,
    allow_delegation=False,
    memory=False
)

def topic_identify_keywords_task(topic: str) -> Task:
    return Task(
        description=(
            f"Analyze the user's provided research topic: '{topic}'. "
            "Identify and list the most effective and precise keywords "
            "for academic citation searches."
        ),
        expected_output="A comma‑separated string of optimized keywords.",
        agent=topic_identify_agent,
        model=llm,
        human_input=True
    )

# —————— Step 4: run Crew to get keywords ——————
task = topic_identify_keywords_task(user_topic)
crew = Crew(agents=[topic_identify_agent], tasks=[task], process=Process.sequential)
raw_topics = crew.kickoff()

# flatten if list
if isinstance(raw_topics, list):
    flat = []
    for item in raw_topics:
        if isinstance(item, list):
            flat.extend(item)
        else:
            flat.append(item)
    user_topic_line = ", ".join(s.strip() for s in flat)
else:
    user_topic_line = str(raw_topics).strip()

# parse into a Python list
topics_list = [t.strip() for t in user_topic_line.split(",") if t.strip()]

# —————— Step 5: dump topics_list to CSV ——————
topics_csv = os.path.join(os.getcwd(), "topics.csv")
with open(topics_csv, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["topic"])
    for t in topics_list:
        writer.writerow([t])

print(f"✅ Wrote topics CSV to {topics_csv}")

# —————— Step 6: ask for paper count & journal ——————
try:
    paper_count = int(input("Enter the number of high-quality research papers needed: ").strip())
except ValueError:
    print("Invalid number; exiting.")
    exit(1)

user_journal = input("Which journal's LaTeX template do you need? ").strip()

# —————— Step 7: write per-run metadata.json ——————
 
print("You can now run subsequent stages pointing them at this output folder.")

import streamlit as st
import subprocess
import os
from dotenv import dotenv_values

st.set_page_config(page_title="Automated Survey Paper Generation", layout="centered")
st.title("Automated Survey Paper Generation")

st.markdown("""
This web interface lets you run the pipeline steps sequentially.
**Step 0**: Enter the required information (topic, paper count, journal) and save them.
**Steps 1–6**: Run the remaining processing scripts.
""")

# -----------------------
# Step 0: User Input Form
# -----------------------
st.subheader("Step 0: Enter Survey Details")
with st.form("user_input_form"):
    user_topic = st.text_input("Enter the topic for the survey paper:")
    paper_count = st.number_input("Enter the number of high-quality research papers needed:", min_value=1, step=1)
    user_journal = st.text_input("Which journal's LaTeX template do you need?")
    
    submitted = st.form_submit_button("Submit Details")
    if submitted:
        # Write the input values to the .env file without overwriting existing API keys
        env_file = ".env"
        existing_env = dotenv_values(env_file)
        if existing_env is None:
            existing_env = {}
        existing_env["TOPIC"] = user_topic
        existing_env["PAPER_COUNT"] = str(paper_count)
        existing_env["JOURNAL"] = user_journal

        with open(env_file, "w") as f:
            for key, value in existing_env.items():
                f.write(f"{key}={value}\n")
        
        st.success("Survey details saved successfully!")
        st.write(f"**Topic:** {user_topic}")
        st.write(f"**Paper Count:** {paper_count}")
        st.write(f"**Journal:** {user_journal}")

# -----------------------
# Helper: Run Command and Store Logs
# -----------------------
logs = {}
def run_command(command_list, step_label):
    """Run a command in a subprocess and store its output."""
    result = subprocess.run(command_list, capture_output=True, text=True)
    logs[step_label] = (result.stdout.strip(), result.stderr.strip())
    return result.returncode

def download_button_for_file(file_path, label):
    """Creates a download button if file exists."""
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            st.download_button(
                label=label,
                data=f,
                file_name=os.path.basename(file_path),
                mime="text/plain"
            )
    else:
        st.warning(f"{os.path.basename(file_path)} not found.")

# -----------------------
# Individual Steps (1 to 6)
# -----------------------

# Combined Steps 1-2: Citation Collection & Deduplication
st.markdown("---")
st.subheader("Step 1-2: Citation Collection & Deduplication")
if st.button("Run Steps 1-2 (Collect & Deduplicate)"):
    code1 = run_command(["python", "1citationcollection.py"], "Step 1")
    code2 = run_command(["bash", "2run_and_switch.sh"], "Step 2")
    
    if code1 == 0 and code2 == 0:
        st.success("Steps 1 and 2 completed successfully!")
    else:
        st.error("There was an error in Steps 1-2. Check logs below.")
    
    with st.expander("View Output: Steps 1-2"):
        stdout1, stderr1 = logs.get("Step 1", ("", ""))
        stdout2, stderr2 = logs.get("Step 2", ("", ""))
        st.write("**Step 1 Output:**")
        st.text(stdout1)
        if stderr1:
            st.error(stderr1)
        st.write("**Step 2 Output:**")
        st.text(stdout2)
        if stderr2:
            st.error(stderr2)
    
    dedup_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deduplicated_citations.csv")
    st.markdown("**Download deduplicated_citations.csv:**")
    download_button_for_file(dedup_file, "Download deduplicated_citations.csv")

# Step 3: Summarize
st.markdown("---")
st.subheader("Step 3: Summarize")
if st.button("Run Step 3: Summarize"):
    code = run_command(["python", "3summary.py"], "Step 3")
    if code == 0:
        st.success("Step 3 completed successfully!")
    else:
        st.error("Step 3 encountered an error.")
    with st.expander("View Output: Step 3"):
        stdout, stderr = logs.get("Step 3", ("", ""))
        st.text(stdout)
        if stderr:
            st.error(stderr)
    summary_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "summaries.csv")
    st.markdown("**Download summaries.csv:**")
    download_button_for_file(summary_file, "Download summaries.csv")

# Step 4: Merge Outlines
st.markdown("---")
st.subheader("Step 4: Merge Outlines")
if st.button("Run Step 4: Merge Outlines"):
    code = run_command(["python", "4merge.py"], "Step 4")
    if code == 0:
        st.success("Step 4 completed successfully!")
    else:
        st.error("Step 4 encountered an error.")
    with st.expander("View Output: Step 4"):
        stdout, stderr = logs.get("Step 4", ("", ""))
        st.text(stdout)
        if stderr:
            st.error(stderr)
    outline_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "survey_paper_outline_one_by_one.md")
    st.markdown("**Download survey_paper_outline_one_by_one.md:**")
    download_button_for_file(outline_file, "Download survey_paper_outline_one_by_one.md")

# Step 5: Writing Sections (Produces 2 files)
st.markdown("---")
st.subheader("Step 5: Writing Sections")
if st.button("Run Step 5: Writing Sections"):
    code = run_command(["python", "5writing.py"], "Step 5")
    if code == 0:
        st.success("Step 5 completed successfully!")
    else:
        st.error("Step 5 encountered an error.")
    with st.expander("View Output: Step 5"):
        stdout, stderr = logs.get("Step 5", ("", ""))
        st.text(stdout)
        if stderr:
            st.error(stderr)
    md_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "completed_research_paper.md")
    tex_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "completed_research_paper.tex")
    st.markdown("**Download Output Files (Step 5):**")
    download_button_for_file(md_file, "Download completed_research_paper.md")
    download_button_for_file(tex_file, "Download completed_research_paper.tex")

# Step 6: Formatting Paper (Produces 2 files)
st.markdown("---")
st.subheader("Step 6: Formatting Paper")
if st.button("Run Step 6: Formatting Paper"):
    code = run_command(["python", "6formatting.py"], "Step 6")
    if code == 0:
        st.success("Step 6 completed successfully!")
    else:
        st.error("Step 6 encountered an error.")
    with st.expander("View Output: Step 6"):
        stdout, stderr = logs.get("Step 6", ("", ""))
        st.text(stdout)
        if stderr:
            st.error(stderr)
    bib_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "references.bib")
    survey_tex_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "survey_paper.tex")
    st.markdown("**Download Output Files (Step 6):**")
    download_button_for_file(bib_file, "Download references.bib")
    download_button_for_file(survey_tex_file, "Download survey_paper.tex")

# -----------------------
# Full Pipeline Button with Progress Bar
# -----------------------
st.markdown("---")
st.subheader("Run Full Pipeline")
if st.button("Run Full Pipeline (Steps 1-6)"):
    progress_bar = st.progress(0)
    # Check if user details are submitted (we assume .env has them)
    if not os.path.exists(".env"):
        st.error("User details not found. Please run Step 0 first.")
    else:
        # Optionally, you can check that TOPIC is in the .env file.
        # Run combined steps sequentially and update progress:
        steps = [
            (["python", "1_citation.py"], "Step 1"),
            (["python", "2deduplicated.py"], "Step 2"),
            (["python", "3_summary.py"], "Step 3"),
            (["python", "4merge.py"], "Step 4"),
            (["python", "5writing.py"], "Step 5"),
            (["python", "6formatting.py"], "Step 6"),
        ]
        total_steps = len(steps)
        for idx, (cmd, label) in enumerate(steps, start=1):
            st.write(f"Running {label}...")
            code = run_command(cmd, label)
            if code != 0:
                st.error(f"{label} encountered an error. Check logs below.")
                break  # Optionally break on error
            progress_bar.progress(int(idx / total_steps * 100))
        else:
            st.success("Full pipeline completed successfully!")
        
        # Display download buttons for output files:
        st.markdown("## Full Pipeline Outputs")
        # Step 2 Output:
        dedup_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deduplicated_citations.csv")
        download_button_for_file(dedup_file, "Download deduplicated_citations.csv")
        # Step 3 Output:
        summary_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "summaries.csv")
        download_button_for_file(summary_file, "Download summaries.csv")
        # Step 4 Output:
        outline_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "survey_paper_outline_one_by_one.md")
        download_button_for_file(outline_file, "Download survey_paper_outline_one_by_one.md")
        # Step 5 Outputs:
        md_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "completed_research_paper.md")
        tex_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "completed_research_paper.tex")
        download_button_for_file(md_file, "Download completed_research_paper.md")
        download_button_for_file(tex_file, "Download completed_research_paper.tex")
        # Step 6 Outputs:
        bib_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "references.bib")
        survey_tex_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "survey_paper.tex")
        download_button_for_file(bib_file, "Download references.bib")
        download_button_for_file(survey_tex_file, "Download survey_paper.tex")

st.markdown("---")
st.markdown("## Instructions")
st.markdown("""
1. Ensure all your pipeline scripts (0userinput.py, 1citationcollection.py, 2run_and_switch.sh, 3summary.py, 4merge.py, 5writing.py, 6formatting.py) are in the same folder as this app.
2. Run `streamlit run app.py` in your terminal.
3. First, fill in the details in **Step 0** and click **Submit Details**.
4. You can run each step individually or click **Run Full Pipeline (Steps 0-6)** to execute everything in sequence.
5. Use the download buttons to retrieve the output files.
""")

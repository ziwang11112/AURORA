import subprocess
import os

pipeline_steps = [
    ("python", "0userinput.py"),                # Step 0: User Input
    ("python", "1_citation.py"),                # Step 1: Citation Collection
    ("python", "2deduplicated.py"),             # Step 2: Deduplication
    ("python", "3_summary.py"),                 # Step 3: Summarization
    ("python", "4merge.py"),                    # Step 4: Outline Merge
    ("python", "5writing-Copy1.py"),            # Step 5: Section Writing
    ("python", "6formatting.py"),               # Step 6: Final Formatting
]

def run_step(step_num, command):
    print(f"\n🔹 Running Step {step_num}: {' '.join(command)}")
    try:
        result = subprocess.run(command, capture_output=True, text=True)
        print("✅ STDOUT:")
        print(result.stdout)
        if result.stderr:
            print("⚠️ STDERR:")
            print(result.stderr)
        if result.returncode != 0:
            print(f"❌ Step {step_num} failed with exit code {result.returncode}.")
            exit(result.returncode)
    except Exception as e:
        print(f"🔥 Error running Step {step_num}: {e}")
        exit(1)

def run_pipeline():
    for idx, cmd in enumerate(pipeline_steps, start=0):
        run_step(idx, cmd)
    print("\n🎉 All pipeline steps (0–6) completed successfully!")

if __name__ == "__main__":
    run_pipeline()

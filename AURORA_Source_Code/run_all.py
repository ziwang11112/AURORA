import subprocess
import time

scripts = [
    
    
    "1_citation.py",
    "2deduplicated.py",
    "3_summary.py",
    "4merge.py",
    "5writing-Copy1.py",
    "6formatting.py",
    "arl_refinement.py"
]

total_start = time.time()

for script in scripts:
    print(f"\n⏱️ Starting {script} ...")
    start_time = time.time()

    result = subprocess.run(["python", script], capture_output=True, text=True)
    
    elapsed = time.time() - start_time
    print(f"✅ Finished {script} in {elapsed:.2f} seconds")

    if result.returncode != 0:
        print(f"❌ Error in {script}:")
        print(result.stderr)
        break

total_elapsed = time.time() - total_start
print(f"\n🎯 All scripts completed in {total_elapsed:.2f} seconds")

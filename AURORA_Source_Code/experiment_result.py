import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import pandas as pd
import numpy as np
import krippendorff

# ── 0. Configuration ──
# Manually define your root path based on where folders are visible
ROOT_DIR = "/scrfs/storage/zwang/home/agentic420"  # Replace with your actual root path if different

BASE_FILES = {
    "SurveyX":     os.path.join(ROOT_DIR, "review_surveyx/all_papers_combined_review.csv"),
    "SurveyForge": os.path.join(ROOT_DIR, "review_surveyforge/all_papers_combined_review.csv"),
    "Baseline":    os.path.join(ROOT_DIR, "review_published/all_papers_combined_review.csv"),
    "Autosurvey":  os.path.join(ROOT_DIR, "review_autosurvey/all_papers_combined_review.csv"),
    "AURORA":      os.path.join(ROOT_DIR, "review_aurora/all_papers_combined_review.csv"),
}

REVIEWERS = ["claude-3.7", "gemini-2.5", "gpt-4.1"]
AGREEMENT_COLS = [
    "Agree (gpt-4.1 vs gemini-2.5)",
    "Agree (gpt-4.1 vs claude-3.7)",
    "Agree (gemini-2.5 vs claude-3.7)"
]
REQUIRED_COLS = ["category", "item"] + REVIEWERS
OUTDIR = "experiment"
os.makedirs(OUTDIR, exist_ok=True)


# Output dict
category_alpha_records = []

for system_name, path in BASE_FILES.items():
    if not os.path.exists(path):
        print(f"⚠️ File not found: {system_name} ({path})")
        continue

    df = pd.read_csv(path)
    df = df[df["category"] != "TOTAL"]

    categories = df["category"].unique()

    for cat in categories:
        cat_df = df[df["category"] == cat]

        try:
            ratings = cat_df[REVIEWERS].T.values  # reviewers x items
            ratings = np.ma.masked_invalid(ratings)
            alpha = krippendorff.alpha(reliability_data=ratings, level_of_measurement='interval')
            category_alpha_records.append((system_name, cat, alpha))
            print(f"✅ {system_name} - {cat}: alpha = {alpha:.3f}")
        except Exception as e:
            print(f"❌ Failed: {system_name} - {cat}: {e}")
            category_alpha_records.append((system_name, cat, np.nan))

# Save category-level results
cat_df = pd.DataFrame(category_alpha_records, columns=["System", "Category", "Krippendorff Alpha"])
os.makedirs("experiment", exist_ok=True)
cat_df.to_csv("experiment/krippendorff_alpha_by_category.csv", index=False)
print("📄 Saved: experiment/krippendorff_alpha_by_category.csv")

# ── 1. Load & concatenate with validation ──
dfs = []
valid_systems = []
for system, path in BASE_FILES.items():
    if not os.path.exists(path):
        print(f"⚠️ Missing file for {system}: {path}")
        continue
    try:
        df = pd.read_csv(path)
        df["System"] = system
        # Log columns for debugging
        print(f"\nColumns in {system} CSV: {df.columns.tolist()}")
        print(f"Expected AGREEMENT_COLS: {AGREEMENT_COLS}")
        # Check required columns
        missing_cols = [col for col in REQUIRED_COLS if col not in df.columns]
        if missing_cols:
            print(f"⚠️ {system} CSV missing required columns: {missing_cols}")
            continue
        # Check agreement columns
        missing_agreement = [col for col in AGREEMENT_COLS if col.strip() not in [c.strip() for c in df.columns]]
        if missing_agreement:
            print(f"⚠️ {system} CSV missing agreement columns: {missing_agreement}")
        dfs.append(df)
        valid_systems.append(system)
    except Exception as e:
        print(f"⚠️ Error loading {system} CSV: {e}")
        continue

if not dfs:
    raise ValueError("No valid CSV files loaded. Check file paths and column names.")

df_all = pd.concat(dfs, ignore_index=True)

# Check if all loaded CSVs have agreement columns
agreement_available = all(all(col.strip() in [c.strip() for c in df.columns] for col in AGREEMENT_COLS) for df in dfs)
if not agreement_available:
    print(f"⚠️ Not all CSVs have agreement columns {AGREEMENT_COLS}. Skipping agreement-related outputs.")

# ── 2. Category-level means ──
cat_df = (
    df_all[df_all["category"] != "TOTAL"]
    .groupby(["System", "category"])[REVIEWERS]
    .mean().round(2)
    .reset_index()
)
cat_df["MeanReviewers"] = cat_df[REVIEWERS].mean(axis=1).round(2)
cat_df.to_csv(f"{OUTDIR}/category_means.csv", index=False)

# Agreement summary (only if columns exist)
if agreement_available:
    agreement_summary = df_all[df_all["category"] != "TOTAL"].groupby(["System", "category"])[AGREEMENT_COLS].mean().mean(axis=1).round(2) * 100
    agreement_pivot = agreement_summary.unstack()
    agreement_pivot.to_latex(
        f"{OUTDIR}/agreement_by_category.tex",
        float_format="%.1f",
        caption="Mean inter-agent agreement (%) by category and system",
        label="tab:agreement_by_category",
        column_format="l" + "c"*agreement_pivot.shape[1]
    )

    # Agreement heatmap
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(agreement_pivot, aspect="auto", vmin=0, vmax=100, cmap="Blues")
    ax.set_xticks(np.arange(len(agreement_pivot.columns)))
    ax.set_xticklabels(agreement_pivot.columns, rotation=45, ha="right")
    ax.set_yticks(np.arange(len(agreement_pivot.index)))
    ax.set_yticklabels(agreement_pivot.index)
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Agreement (%)")
    ax.set_title("Inter-Agent Agreement by Category and System")
    plt.tight_layout()
    plt.savefig(f"{OUTDIR}/agreement_heatmap.png", dpi=300)
    plt.close()

    # LaTeX figure code for agreement heatmap
    with open(f"{OUTDIR}/agreement_heatmap.tex", "w") as f:
        f.write(r"""
\begin{figure}[h]
    \centering
    \includegraphics[width=0.8\textwidth]{agreement_heatmap.png}
    \caption{Heatmap of mean inter-agent agreement percentages across categories and systems, based on pairwise reviewer agreement (Claude-3.7, Gemini-2.5, GPT-4.1).}
    \label{fig:agreement_heatmap}
\end{figure}
""")

# Paper variability
paper_variability = df_all[df_all["category"] != "TOTAL"].groupby(["System", "category"])[REVIEWERS].agg(lambda x: f"{x.min():.1f}–{x.max():.1f}").reset_index()
paper_variability["MeanReviewers Range"] = df_all[df_all["category"] != "TOTAL"].groupby(["System", "category"])[REVIEWERS].mean().agg(lambda x: f"{x.min():.1f}–{x.max():.1f}")
paper_variability_pivot = paper_variability.pivot(index="category", columns="System", values="MeanReviewers Range")
paper_variability_pivot.to_latex(
    f"{OUTDIR}/paper_variability.tex",
    caption="Range of mean reviewer scores by category and system across multiple papers",
    label="tab:paper_variability",
    column_format="l" + "c"*paper_variability_pivot.shape[1]
)

# ── 3. Heatmap of MeanReviewers ──
heat = cat_df.pivot(index="category", columns="System", values="MeanReviewers")
fig, ax = plt.subplots(figsize=(8,6))
im = ax.imshow(heat, aspect="auto", vmin=0, vmax=5, cmap="viridis")
ax.set_xticks(np.arange(len(heat.columns)))
ax.set_xticklabels(heat.columns, rotation=45, ha="right")
ax.set_yticks(np.arange(len(heat.index)))
ax.set_yticklabels(heat.index)
cbar = fig.colorbar(im, ax=ax)
cbar.set_label("Mean Score")
ax.set_title("Heatmap of Mean Reviewer Scores by Category and System")
plt.tight_layout()
plt.savefig(f"{OUTDIR}/heatmap_mean_reviewers.png", dpi=300)
plt.close()

# ── 4. Bar-charts & LaTeX per reviewer + mean ──
for metric in REVIEWERS + ["MeanReviewers"]:
    pivot = cat_df.pivot(index="category", columns="System", values=metric)
    with open(f"{OUTDIR}/{metric}_by_category.tex", "w") as f:
        f.write(pivot.to_latex(
            float_format="%.2f",
            caption=f"{metric} scores by system and rubric category",
            label=f"tab:{metric}_by_category",
            column_format="l" + "c"*pivot.shape[1]
        ))
    ax = pivot.plot.bar(
        figsize=(10,5), 
        title=f"{metric} Category Means",
        ylabel="Score", xlabel="Category"
    )
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(f"{OUTDIR}/{metric}_by_category.png", dpi=300)
    plt.close()

# ── 5. Radar charts per reviewer + mean ──
categories = cat_df["category"].unique().tolist()
angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
angles += angles[:1]
systems = cat_df["System"].unique().tolist()
colors = plt.cm.tab10.colors
metrics = REVIEWERS + ["MeanReviewers"]
full_category_labels = {
    "Analysis": "Analysis",
    "Literature": "Literature",
    "Organization": "Organization",
    "Originality": "Originality",
    "Presentation": "Presentation",
    "References": "References",
    "Scope": "Scope"
}
metric_names = {
    "claude-3.7": "Claude 3.7 (Sonnet)",
    "gemini-2.5": "Gemini 2.5 Pro",
    "gpt-4.1": "GPT-4.1",
    "MeanReviewers": "Mean of Agents"
}


# ── Combined 2x2 radar chart ──
fig, axes = plt.subplots(2, 2, figsize=(15, 12), subplot_kw=dict(polar=True))
axes = axes.flatten()
for ri, metric in enumerate(metrics):
    ax = axes[ri]
    for si, system in enumerate(systems):
        vals = (
            cat_df[cat_df["System"] == system]
            .set_index("category")
            .loc[categories, metric]
            .tolist()
        )
        vals += vals[:1]
        ax.plot(angles, vals, label=system, color=colors[si], linewidth=2)
        ax.fill(angles, vals, color=colors[si], alpha=0.15)

    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_thetagrids(np.degrees(angles[:-1]), categories)
    for label in ax.get_xticklabels():
        label.set_fontsize(10)
        label.set_horizontalalignment('center')
        label.set_verticalalignment('center_baseline')
        if "References" in label.get_text():
            label.set_horizontalalignment('right')   # Or 'center'
        elif "Organization" in label.get_text():
            label.set_horizontalalignment('left')  # Or 'center'
        elif "Literature" in label.get_text():
            label.set_horizontalalignment('left') 
        
    ax.set_ylim(0, 5)
    # Show radial (concentric) gridlines
    ax.yaxis.grid(True, linestyle='--', linewidth=0.6, color='gray')

    # Show angular (spoke) lines
    ax.xaxis.grid(True, linestyle='--', linewidth=0.6, color='gray')

    ax.set_title(metric_names.get(metric, metric), fontsize=12, fontweight='bold', y=1.1)

    if ri == 0:
        ax.legend(loc="upper right", bbox_to_anchor=(1.4, 1.1))

fig.suptitle("Combined Radar Charts by Reviewer and Mean", fontsize=16, y=1.08)
plt.tight_layout()
plt.savefig(f"{OUTDIR}/radar_combined.png", dpi=600)
plt.close()


# ── 6. TOTAL-score means ──
tot_df = df_all[df_all["category"] == "TOTAL"]
if not tot_df.empty:
    total_means = (
        tot_df.groupby("System")[REVIEWERS]
        .mean().round(2).reset_index()
    )
    total_means["MeanAllReviewers"] = total_means[REVIEWERS].mean(axis=1).round(2)
    total_means.to_csv(f"{OUTDIR}/total_means.csv", index=False)

    # Score range: use xs() on full score_ranges DataFrame
    score_ranges = tot_df.groupby("System")[REVIEWERS].agg(['min', 'max'])
    mins_df = score_ranges.xs('min', level=1, axis=1)
    maxs_df = score_ranges.xs('max', level=1, axis=1)
    score_range_strings = []
    for system in score_ranges.index:
        min_val = mins_df.loc[system].min()
        max_val = maxs_df.loc[system].max()
        score_range_strings.append(f"{min_val:.1f}–{max_val:.1f}")
    total_means["Score Range"] = score_range_strings

    # Agreement
    if agreement_available:
        agreement_vals = (
            df_all[df_all["category"] != "TOTAL"]
            .groupby("System")[AGREEMENT_COLS]
            .mean().mean(axis=1).round(2) * 100
        )
        total_means["Agreement (%)"] = total_means["System"].map(agreement_vals)
        total_means = total_means[["System", *REVIEWERS, "MeanAllReviewers", "Agreement (%)", "Score Range"]]
        column_format = "lcccccp{2cm}"
    else:
        total_means = total_means[["System", *REVIEWERS, "MeanAllReviewers", "Score Range"]]
        column_format = "lccccp{2cm}"

    total_means.to_latex(
        f"{OUTDIR}/total_summary.tex",
        index=False,
        float_format="%.2f",
        caption="Mean total scores, score ranges, and inter-agent agreement by system",
        label="tab:total_summary",
        column_format=column_format
    )

    ax = total_means.plot.bar(
        x="System",
        y=REVIEWERS + ["MeanAllReviewers"],
        figsize=(10, 5),
        ylabel="Total Score",
        title="Mean TOTAL Scores per System"
    )
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(f"{OUTDIR}/mean_total_scores.png", dpi=600)
    plt.close()

else:
    print("⚠️ No TOTAL rows found — skipping total-score summary.")

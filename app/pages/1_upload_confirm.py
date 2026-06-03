"""
Page 1 — Upload + schema confirmation
Owner: Ana Valderrama
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from src.data_prep import run_pipeline
from src.zip_handler import (
    auto_detect_schema,
    confirm_and_save,
    load_upload,
    render_schema_confirmation,
)

st.header("Step 1: Upload your marketing dataset")
st.markdown(
    """
Upload your dataset in any of these formats:
- **`.zip` file** containing your CSV + an optional `.xlsx` data dictionary
- **`.csv` file** directly

The file should include a date column, spend columns per channel, and a conversions column.
"""
)

uploaded_file = st.file_uploader(
    label="Upload dataset (.zip or .csv)",
    type=["zip", "csv"],
    help="Accepted: .zip (with CSV + optional XLSX dictionary) or bare .csv. Maximum 200 MB.",
)

if uploaded_file is not None:
    with st.spinner("Reading your dataset..."):
        try:
            result = load_upload(uploaded_file.read(), uploaded_file.name)
        except ValueError as e:
            st.error(f"Could not read the file: {e}")
            st.stop()

    csv_files = result["csv_files"]
    dictionary = result["dictionary"]

    if len(csv_files) > 1:
        selected = st.selectbox(
            "Multiple CSV files found in your zip. Which one should we use?",
            options=list(csv_files.keys()),
        )
    else:
        selected = list(csv_files.keys())[0]

    df = csv_files[selected]

    if dictionary is not None:
        st.success(f"Data dictionary found and loaded ({len(dictionary)} entries).")
        with st.expander("Preview data dictionary"):
            st.dataframe(dictionary.head(20), use_container_width=True)
    else:
        st.info("No data dictionary found. Column roles will be auto-detected from column names.")

    profile = auto_detect_schema(df, selected, dictionary=dictionary)
    confirmation_data = render_schema_confirmation(profile)

    st.success(f"Found **{profile.n_rows:,} rows** and **{profile.n_columns} columns** in `{selected}`.")

    st.subheader("Dataset profile")
    col1, col2, col3 = st.columns(3)
    col1.metric("Rows", f"{profile.n_rows:,}")
    col2.metric("Columns", profile.n_columns)
    col3.metric("Exact duplicates", profile.duplicate_count)

    st.subheader("Column roles detected")
    if confirmation_data.get("columns_table"):
        st.dataframe(
            pd.DataFrame(confirmation_data["columns_table"]),
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("Marketing channels")
    st.markdown(
        f"**Channels to model:** {', '.join(profile.detected_channels) or 'None detected'}"
    )
    if profile.dropped_channels:
        st.markdown(f"**Channels excluded** (too sparse): {', '.join(profile.dropped_channels)}")

    if confirmation_data.get("warnings"):
        for w in confirmation_data["warnings"]:
            st.warning(w)

    st.subheader("Confirm before proceeding")
    st.markdown(confirmation_data.get("confirmation_prompt", ""))

    with st.form("confirm_schema"):
        target_col = st.selectbox(
            "Target variable (what we're optimizing for):",
            options=profile.target_candidates,
            index=0,
        )
        budget_input = st.number_input(
            "Total annual budget ($):",
            min_value=1000,
            max_value=10_000_000,
            value=50_000,
            step=1000,
        )
        confirmed = st.form_submit_button("Confirm and proceed to analysis")

    if confirmed:
        with st.spinner("Saving confirmed dataset..."):
            df, raw_path = confirm_and_save(df, profile)

        with st.spinner("Cleaning dataset..."):
            pipeline_result = run_pipeline(raw_path=raw_path)

        st.session_state.raw_path = raw_path
        st.session_state.cleaned_df = pipeline_result["ready_df"]
        st.session_state.train_df = pipeline_result["train_df"]
        st.session_state.test_df = pipeline_result["test_df"]
        st.session_state.eda_report = pipeline_result["eda_report"]
        st.session_state.schema_profile = profile
        st.session_state.upload_complete = True
        st.session_state.schema_confirmed = True
        st.session_state.phase = "analysis"
        st.session_state.confirmed_target = target_col
        st.session_state.confirmed_budget = budget_input

        st.success("Dataset cleaned and ready.")

        st.subheader("Download your cleaned files")
        c1, c2, c3 = st.columns(3)
        c1.download_button(
            label="Full cleaned dataset (mmm_ready.csv)",
            data=pipeline_result["ready_csv_bytes"],
            file_name="mmm_ready.csv",
            mime="text/csv",
        )
        c2.download_button(
            label="Training split (mmm_train.csv)",
            data=pipeline_result["train_csv_bytes"],
            file_name="mmm_train.csv",
            mime="text/csv",
        )
        c3.download_button(
            label="Holdout split (mmm_test.csv)",
            data=pipeline_result["test_csv_bytes"],
            file_name="mmm_test.csv",
            mime="text/csv",
        )

        st.subheader("EDA — Exploratory Data Analysis")
        eda = pipeline_result["eda_report"]
        tab1, tab2, tab3, tab4 = st.tabs(
            ["Spend over time", "Channel coverage", "Target variable", "Correlation"]
        )
        with tab1:
            st.plotly_chart(eda["spend_over_time"], use_container_width=True)
        with tab2:
            st.plotly_chart(eda["channel_coverage"], use_container_width=True)
            st.plotly_chart(eda["null_heatmap"], use_container_width=True)
        with tab3:
            st.plotly_chart(eda["target_over_time"], use_container_width=True)
        with tab4:
            st.plotly_chart(eda["correlation_matrix"], use_container_width=True)
            st.plotly_chart(eda["spend_distribution"], use_container_width=True)

        with st.expander("Summary statistics"):
            st.dataframe(eda["summary_stats"], use_container_width=True)

        st.info(
            f"Dataset: **{eda['n_rows']:,} rows** · "
            f"**{eda['n_channels']} channels** · "
            f"**{eda['timeseries_count']} time series** · "
            f"Date range: {eda['date_range'][0]} → {eda['date_range'][1]}"
        )

        st.divider()
        if st.button("Proceed to Step 2: Backward Analysis"):
            st.switch_page("pages/2_backward_analysis.py")

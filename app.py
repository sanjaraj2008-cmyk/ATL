import json
import streamlit as st
import pandas as pd
from core.audit_engine import AuditEngine
from core.schemas import ClaimStatus, Severity, ReasonCode, DOMZone, AuditState

st.set_page_config(
    page_title="Ad-to-Landing-Page Message Match Auditor",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Mobile-Friendly / Clean CSS
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 16px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border-left: 5px solid #1E88E5;
        margin-bottom: 12px;
    }
    .liability-banner {
        background-color: #ffebee;
        color: #c62828;
        border: 2px solid #ef5350;
        border-radius: 8px;
        padding: 14px;
        font-weight: bold;
        margin-bottom: 20px;
    }
    .badge-supported {
        background-color: #e8f5e9;
        color: #2e7d32;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 0.85em;
        font-weight: 600;
    }
    .badge-contradicted {
        background-color: #ffebee;
        color: #c62828;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 0.85em;
        font-weight: 600;
    }
    .badge-not-found {
        background-color: #fff3e0;
        color: #e65100;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 0.85em;
        font-weight: 600;
    }
    .badge-partial {
        background-color: #ede7f6;
        color: #512da8;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 0.85em;
        font-weight: 600;
    }
    .evidence-box {
        background-color: #f1f8e9;
        border-left: 4px solid #7cb342;
        padding: 10px 14px;
        border-radius: 4px;
        margin-top: 8px;
        font-style: italic;
    }
</style>
""", unsafe_allow_html=True)

# Load benchmark presets
@st.cache_data
def load_presets():
    with open("samples/benchmark_cases.json", "r") as f:
        return json.load(f)

presets = load_presets()

# Sidebar: Inputs & Test Presets
st.sidebar.title("🎯 Auditor Controls")

st.sidebar.markdown("### ⚡ Benchmark Presets")
preset_names = ["(Custom Input)"] + [p["title"] for p in presets]
selected_preset = st.sidebar.selectbox("Load Sample Case:", preset_names)

selected_case = None
if selected_preset != "(Custom Input)":
    selected_case = next(p for p in presets if p["title"] == selected_preset)

default_headline = selected_case["ad_headline"] if selected_case else "Get a 30-day free trial"
default_desc = selected_case["ad_description"] if selected_case else "Start using our project management software today. No credit card required."
default_html = selected_case["html"] if selected_case else "<html><body><h1>Start your free 7-day trial</h1><p>Enter your payment details to continue.</p></body></html>"

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙ Audit Mode")
st.sidebar.info("🔒 **Deterministic Offline Engine Active**\n100% evidence-grounded. Zero hallucination tolerance.")

# Main Screen Header
st.title("🎯 Ad-to-Landing-Page Message Match Auditor")
st.caption("Evidence-grounded marketing compliance auditor with two-tier quote verification & normalized scoring.")

# Input Form
with st.expander("📝 Input Advertisement & Landing Page Snapshot", expanded=(selected_case is None)):
    col1, col2 = st.columns([1, 1])
    with col1:
        ad_headline = st.text_input("Ad Headline", value=default_headline)
        ad_description = st.text_area("Ad Description / Body Copy", value=default_desc, height=100)
    with col2:
        uploaded_file = st.file_uploader("Upload Landing Page HTML Snapshot (Optional)", type=["html", "htm"])
        if uploaded_file:
            landing_html = uploaded_file.read().decode("utf-8", errors="ignore")
        else:
            landing_html = st.text_area("Or Paste Landing Page HTML", value=default_html, height=138)

run_audit = st.button("🚀 Run Evidence-Grounded Audit", type="primary", use_container_width=True)

if run_audit or selected_case is not None:
    engine = AuditEngine()
    result = engine.audit(ad_headline, ad_description, landing_html)

    if result.audit_state == AuditState.FAILED_UNREADABLE_INPUT:
        st.error(f"❌ Audit Failed: {', '.join(result.audit_warnings)}")
    else:
        st.markdown("---")
        # Critical Marketing Liability Alert
        if result.has_critical_marketing_liability:
            st.markdown("""
            <div class="liability-banner">
                🚨 CRITICAL MARKETING LIABILITY DETECTED: One or more material promises (e.g. pricing, trial duration, or friction) are explicitly contradicted by verified page evidence.
            </div>
            """, unsafe_allow_html=True)

        # Overview KPI Metrics
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            score_color = "🟢" if result.match_score >= 85 else ("🟡" if result.match_score >= 60 else "🔴")
            st.metric(label="Match Score", value=f"{result.match_score}/100", delta=result.grade)
        with m2:
            st.metric(label="Evidence Coverage", value=f"{result.evidence_coverage_index}%", help="% of ad promises with assessable page evidence.")
        with m3:
            prom_val = f"{result.evidence_prominence_index}%" if result.evidence_prominence_index is not None else "N/A"
            st.metric(label="Evidence Prominence", value=prom_val, help="Prominence of verified evidence (above-the-fold vs footer).")
        with m4:
            validity_val = f"{result.evidence_validity_rate}%" if result.evidence_validity_rate is not None else "N/A"
            st.metric(label="Evidence Validity Rate", value=validity_val, help="Quotations verified in source DOM (100% target).")

        # Findings Section
        st.markdown(f"### 📋 Audit Findings ({len(result.findings)} Claims Assessed)")

        for idx, finding in enumerate(result.findings, start=1):
            status_badge_class = {
                ClaimStatus.SUPPORTED: "badge-supported",
                ClaimStatus.CONTRADICTED: "badge-contradicted",
                ClaimStatus.NOT_FOUND: "badge-not-found",
                ClaimStatus.PARTIALLY_SUPPORTED: "badge-partial",
                ClaimStatus.AMBIGUOUS: "badge-not-found"
            }.get(finding.status, "badge-partial")

            severity_icon = "🔴" if finding.severity == Severity.CRITICAL or finding.severity == Severity.HIGH else ("🟡" if finding.severity == Severity.MEDIUM else "🟢")

            with st.container():
                st.markdown(f"""
                <div class="metric-card">
                    <h4>{severity_icon} Finding #{idx}: {finding.ad_claim_text}</h4>
                    <span class="{status_badge_class}">{finding.status.value}</span> &nbsp;
                    <small><b>Reason:</b> {finding.reason_code.value} | <b>Materiality:</b> {finding.claim_materiality.value} | <b>Severity:</b> {finding.severity.value}</small>
                    <p style="margin-top: 8px;">{finding.explanation}</p>
                </div>
                """, unsafe_allow_html=True)

                if finding.primary_evidence:
                    verified_icon = "✔ Verified against source DOM" if finding.primary_evidence.is_verified else "❌ Unverified"
                    st.markdown(f"""
                    <div class="evidence-box">
                        <b>Page Evidence Quote:</b> “{finding.primary_evidence.quote}”<br>
                        <small>📍 <b>Location:</b> {finding.primary_evidence.dom_zone.value} (Tag: <code>&lt;{finding.primary_evidence.tag_name}&gt;</code>, Block: <code>{finding.primary_evidence.block_id}</code>) | {verified_icon}</small>
                    </div>
                    """, unsafe_allow_html=True)

                # Recommended Fixes
                fix_col1, fix_col2 = st.columns(2)
                with fix_col1:
                    st.info(f"💡 **Suggested Ad Fix:**\n{finding.recommended_ad_fix}")
                with fix_col2:
                    st.success(f"🛠 **Suggested Landing Page Fix:**\n{finding.recommended_page_fix}")

        # Export Report Section
        st.markdown("---")
        st.subheader("📥 Export Audit Report")

        export_data = []
        for f in result.findings:
            export_data.append({
                "Claim ID": f.claim_id,
                "Ad Claim Text": f.ad_claim_text,
                "Status": f.status.value,
                "Reason Code": f.reason_code.value,
                "Materiality": f.claim_materiality.value,
                "Severity": f.severity.value,
                "Evidence Quote": f.primary_evidence.quote if f.primary_evidence else "None",
                "Evidence Zone": f.primary_evidence.dom_zone.value if f.primary_evidence else "None",
                "Quote Verified": f.primary_evidence.is_verified if f.primary_evidence else False,
                "Explanation": f.explanation,
                "Suggested Ad Fix": f.recommended_ad_fix,
                "Suggested Page Fix": f.recommended_page_fix
            })

        df_export = pd.DataFrame(export_data)

        d_col1, d_col2 = st.columns(2)
        with d_col1:
            csv_str = df_export.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Report (CSV)", data=csv_str, file_name="message_match_audit_report.csv", mime="text/csv", use_container_width=True)
        with d_col2:
            json_str = result.model_dump_json(indent=2)
            st.download_button("📥 Download Report (JSON)", data=json_str, file_name="message_match_audit_report.json", mime="application/json", use_container_width=True)

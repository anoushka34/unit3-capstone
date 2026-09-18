"""
make_sample_pdf.py

Generates the sample governance policy PDF locally - no file transfer
needed. Run this once from your project root; it creates
data/sample_governance_policy.pdf directly.

Install once:
    pip install reportlab --break-system-packages
"""

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import os

os.makedirs("data", exist_ok=True)

doc = SimpleDocTemplate("data/sample_governance_policy.pdf", pagesize=letter)
styles = getSampleStyleSheet()
story = []

story.append(Paragraph("DATA GOVERNANCE &amp; RETENTION POLICY", styles['Title']))
story.append(Paragraph("Capstone Project - Sample Policy Document", styles['Normal']))
story.append(Spacer(1, 20))

story.append(Paragraph("1. Customer Retention Strategy", styles['Heading2']))
story.append(Paragraph(
    "Our retention strategy targets a maximum acceptable monthly churn rate of 5%. "
    "Any month where churn exceeds this threshold requires a root-cause review by "
    "the analytics team within 10 business days. Retention efforts prioritize "
    "high-engagement users (top quartile by weekly session count) and focus on "
    "proactive outreach rather than reactive discounting.", styles['Normal']))
story.append(Spacer(1, 12))

story.append(Paragraph("2. Data Governance Requirements", styles['Heading2']))
story.append(Paragraph(
    "All structured datasets ingested into the data catalog must include the "
    "following metadata fields at minimum: source_system, ingestion_date, "
    "data_owner, retention_period_days, pii_classification (none, low, medium, "
    "or high). Datasets missing any of the above fields are considered "
    "non-compliant and must be flagged for remediation before being used in "
    "downstream reporting or made available to the AI query layer.", styles['Normal']))
story.append(Spacer(1, 12))

story.append(Paragraph("3. Schema Cataloging", styles['Heading2']))
story.append(Paragraph(
    "All datasets must be registered in the central schema catalog (AWS Glue "
    "Data Catalog) prior to use. Manual registration is acceptable when "
    "automated discovery tools are unavailable, provided the resulting schema "
    "is reviewed for accuracy against the source data.", styles['Normal']))

doc.build(story)
print("Created data/sample_governance_policy.pdf")
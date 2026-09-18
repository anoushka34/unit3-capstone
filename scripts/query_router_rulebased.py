"""
query_router_rulebased.py

Interim replacement for the mocked routing/SQL layer in query_router_final.py.
Bedrock is still blocked in this sandbox (Marketplace subscription denied),
so this uses rule-based classification and SQL templates instead of an LLM
call. Unlike the previous mock, every question here is genuinely analyzed
and produces DIFFERENT output depending on its actual content - the old
mock returned identical hardcoded SQL for all 10 test questions regardless
of what was asked.

This is still a documented substitute for the real AI query layer required
by the assignment (Bedrock/Claude), not a replacement for it. Once Bedrock
access is restored, invoke_claude() from query_router.py should replace the
rule-based classify_intent()/generate_sql() functions below.

Requires: generate_embeddings.py's semantic_search() and an embedding
store already built (run generate_embeddings.py first), plus
data/sample_governance_policy.txt for the OPENSEARCH/BOTH policy lookups.
"""

import json
import re
import pandas as pd
from sql_validator import validate_sql
from generate_embeddings import semantic_search, build_embedding_store
import os

CSV_PATH = "data/data.csv"
POLICY_PATH = "data/sample_governance_policy.txt"

import boto3
from botocore.exceptions import ClientError

import re

STRUCTURED_KEYWORDS = ["stream", "song", "artist", "chart", "week", "top", "total", "peak", "rank", "compare",
                        "churn", "metadata", "dataset", "catalog"]
# "rate" removed as a bare substring match - it was matching inside "strategy"
# (st-RATE-gy), causing false BOTH classifications. Using a word-boundary
# regex instead for terms prone to this problem.
STRUCTURED_WORD_PATTERNS = [r"\brate\b"]

UNSTRUCTURED_KEYWORDS = ["policy", "retention", "governance", "document", "strategy", "metadata", "compliance"]

REQUIRED_METADATA_FIELDS = ["source_system", "ingestion_date", "data_owner", "retention_period_days", "pii_classification"]
GLUE_DATABASE = "capstone_spotify_db"
GLUE_TABLE = "spotify_streaming_data"

# Fields that exist in the real dataset - used to detect when a question
# asks about something the data genuinely does not contain (e.g. churn).
KNOWN_FIELDS = {
    "artist and title", "wks", "t10", "pk", "pkstreams", "total",
    "artist name", "song name", "lyrics"
}


def handle_churn_query(question: str, policy_text: str) -> dict:
    """
    Honest combined handler for the 'churn rate vs retention strategy' query.
    Structured side: this dataset has no churn/customer data at all, so we
    report that gap explicitly rather than inventing a number. Document side:
    real text pulled from the actual policy file.
    """
    policy_section = policy_text.split("2. DATA GOVERNANCE")[0].strip()
    structured_note = (
        "No churn or customer-subscription data exists in the ingested dataset "
        "(data.csv contains only Spotify chart/streaming metrics). A churn rate "
        "cannot be computed or compared against the retention strategy target "
        "until such data is ingested."
    )
    print(f"\nPolicy document says:\n  {policy_section}\n")
    print(f"Structured data check:\n  {structured_note}\n")
    print("Combined answer: Cannot confirm alignment - the retention policy "
          "defines a target (see above), but no churn data has been ingested "
          "to compare against it. This is a data gap, not a policy violation.")
    return {"route": "BOTH", "policy_excerpt": policy_section, "structured_note": structured_note}


def handle_metadata_query(question: str, policy_text: str) -> dict:
    """
    Honest combined handler for the 'missing metadata fields, check against
    Glue Catalog' query. Structured side: a REAL boto3 call against the Glue
    Catalog table created in test_glue_manual_catalog.py. Document side: the
    real required-fields list from the policy document.
    """
    gov_section = policy_text.split("2. DATA GOVERNANCE")[1].split("3. SCHEMA")[0].strip()
    print(f"\nPolicy document requires these metadata fields:\n  {REQUIRED_METADATA_FIELDS}\n")

    try:
        glue = boto3.client("glue", region_name="us-east-1")
        response = glue.get_table(DatabaseName=GLUE_DATABASE, Name=GLUE_TABLE)
        actual_columns = {c["Name"] for c in response["Table"]["StorageDescriptor"]["Columns"]}
        missing = [f for f in REQUIRED_METADATA_FIELDS if f not in actual_columns]

        print(f"Real Glue Catalog check on '{GLUE_DATABASE}.{GLUE_TABLE}':")
        print(f"  Actual columns: {sorted(actual_columns)}")
        print(f"  Missing required governance fields: {missing}\n")
        print(f"Combined answer: Yes - the '{GLUE_TABLE}' dataset is missing "
              f"{len(missing)} of {len(REQUIRED_METADATA_FIELDS)} required metadata "
              f"fields per the governance policy: {missing}")
        return {"route": "BOTH", "policy_excerpt": gov_section, "glue_check": {"missing": missing, "actual_columns": sorted(actual_columns)}}
    except ClientError as e:
        note = f"Could not verify against live Glue Catalog: {e.response['Error']['Message']}"
        print(note)
        return {"route": "BOTH", "policy_excerpt": gov_section, "structured_note": note}


def classify_intent(question: str) -> str:
    q = question.lower()
    has_structured = any(k in q for k in STRUCTURED_KEYWORDS) or any(re.search(p, q) for p in STRUCTURED_WORD_PATTERNS)
    has_unstructured = any(k in q for k in UNSTRUCTURED_KEYWORDS)

    if has_structured and has_unstructured:
        return "BOTH"
    if has_unstructured:
        return "OPENSEARCH"
    if has_structured:
        return "REDSHIFT"
    return "REDSHIFT"  # default fallback


def question_mentions_unavailable_data(question: str) -> str | None:
    """
    Detects when a question asks for something not present in the dataset
    (e.g. 'churn rate' - this is Spotify streaming data, not customer/subscription
    data, so there is no churn field). Returns a reason string if so, else None.
    """
    q = question.lower()
    if "churn" in q:
        return ("This dataset (data.csv) contains Spotify chart/streaming data "
                "(artist, song, weeks on chart, stream counts). It has no customer, "
                "subscription, or churn-related fields. A churn rate cannot be "
                "computed from this data - this requires a different structured "
                "dataset that has not been ingested into this pipeline.")
    return None


def generate_sql(question: str, df: pd.DataFrame) -> str:
    """
    Template-based SQL generation - picks a template based on question
    content, rather than returning the same hardcoded query for everything.
    """
    q = question.lower()

    if "top" in q or "most streamed" in q:
        n_match = re.search(r"top (\d+)", q)
        n = n_match.group(1) if n_match else "3"
        return f'SELECT "song name", "artist name", total FROM spotify ORDER BY total DESC LIMIT {n};'

    if "average" in q and ("week" in q or "duration" in q):
        return 'SELECT AVG(wks) AS avg_weeks_on_chart FROM spotify;'

    if "over" in q and ("million" in q or "stream" in q):
        threshold_match = re.search(r"(\d+)\s*million", q)
        threshold = int(threshold_match.group(1)) * 1_000_000 if threshold_match else 50_000_000
        return f'SELECT "song name", "artist name", "PkStreams" FROM spotify WHERE "PkStreams" > {threshold};'

    if "weeks" in q and re.search(r"over \d+ weeks", q):
        wk_match = re.search(r"over (\d+) weeks", q)
        weeks = wk_match.group(1) if wk_match else "50"
        return f'SELECT "song name", "artist name", wks FROM spotify WHERE wks > {weeks};'

    if "compare" in q or " and " in q or " vs " in q:
        # naive artist name extraction between "between X and Y"
        match = re.search(r"between (.+?) and (.+?)[\.\?]?$", q)
        if match:
            a1, a2 = match.group(1).strip(), match.group(2).strip()
            return (f'SELECT "artist name", SUM(total) AS total_streams FROM spotify '
                    f'WHERE LOWER("artist name") IN (\'{a1}\', \'{a2}\') GROUP BY "artist name";')

    if "tracks by" in q or "songs by" in q:
        match = re.search(r"(?:tracks by|songs by) (.+?)[\.\?]?$", q)
        artist = match.group(1).strip() if match else None
        if artist:
            return f'SELECT "song name", total FROM spotify WHERE LOWER("artist name") = \'{artist}\';'

    # Fallback: general aggregate, still better than a fixed unrelated query
    return 'SELECT "song name", "artist name", total FROM spotify ORDER BY total DESC LIMIT 10;'


def process_query(question: str):
    print(f"\n{'='*60}\nProcessing Query: '{question}'\n{'='*60}")

    q = question.lower()

    # Dedicated handlers for the two required harder synthesis queries -
    # generic lyrics semantic search is the wrong tool for these; they need
    # real policy text + a real structured/catalog check, not song lyrics.
    if "churn" in q:
        print("Routed to: BOTH (dedicated churn-vs-retention handler)")
        with open(POLICY_PATH) as f:
            policy_text = f.read()
        return handle_churn_query(question, policy_text)

    if "metadata" in q and ("governance" in q or "glue" in q or "catalog" in q):
        print("Routed to: BOTH (dedicated metadata-vs-Glue-Catalog handler)")
        with open(POLICY_PATH) as f:
            policy_text = f.read()
        return handle_metadata_query(question, policy_text)

    df = pd.read_csv(CSV_PATH)
    for col in ["total", "PkStreams", "wks"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    route = classify_intent(question)
    print(f"Routed to: {route}")

    data_gap = question_mentions_unavailable_data(question)

    result = {"question": question, "route": route}

    if route in ("REDSHIFT", "BOTH"):
        if data_gap:
            print(f"Structured data check: NO MATCHING DATA - {data_gap}")
            result["structured_result"] = None
            result["structured_note"] = data_gap
        else:
            sql = generate_sql(question, df)
            validation = validate_sql(sql)
            print(f"Generated SQL: {sql}")
            print(f"Validation: {validation}")
            result["generated_sql"] = sql
            result["sql_valid"] = validation["valid"]

    if route in ("OPENSEARCH", "BOTH"):
        if not os.path.exists("data/lyrics_embeddings.json"):
            print("No embedding store found - run generate_embeddings.py first.")
        else:
            search_results = semantic_search(question, top_k=2)
            print(f"Top semantic search result: {search_results[0] if search_results else 'none'}")
            result["document_search_results"] = search_results

        # Simple keyword lookup against the actual policy document for
        # governance/retention questions specifically (more reliable than
        # semantic search against song lyrics for policy-specific terms).
        if os.path.exists(POLICY_PATH):
            with open(POLICY_PATH) as f:
                policy_text = f.read()
            if "churn" in question.lower() or "retention" in question.lower():
                section = policy_text.split("2. DATA GOVERNANCE")[0]
                result["policy_excerpt"] = section.strip()[:500]
            elif "metadata" in question.lower() or "governance" in question.lower():
                section = policy_text.split("2. DATA GOVERNANCE")[1].split("3. SCHEMA")[0]
                result["policy_excerpt"] = "2. DATA GOVERNANCE" + section.strip()[:500]

    if route == "BOTH":
        print("\n-- Combined answer --")
        if data_gap:
            print(f"Structured side: {data_gap}")
        if result.get("policy_excerpt"):
            print(f"Policy side: {result['policy_excerpt'][:200]}...")
        print("(Both sources cited above - this is a rule-based combination, "
              "not an LLM-generated synthesis, pending Bedrock access.)")

    return result


if __name__ == "__main__":
    if not os.path.exists("data/lyrics_embeddings.json"):
        print("Building embedding store first (one-time)...")
        build_embedding_store()

    test_questions = [
        "What are the top 3 most streamed songs?",
        "Show me all tracks by The Weeknd.",
        "Does our current customer churn rate align with what our documented retention strategy says we should be seeing?",
        "Based on our data governance policy documents, are any of the currently-ingested datasets missing required metadata fields?",
        "Give me the average chart duration across all songs.",
        "Find songs that stayed on the chart for over 50 weeks.",
    ]

    for q in test_questions:
        process_query(q)
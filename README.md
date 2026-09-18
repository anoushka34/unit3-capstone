# Unit 3 Capstone: Intelligent Document Search & Pipeline Architecture

## 1. Project Overview

This project designs an intelligent document search and analytics pipeline integrating cloud storage, automated schema discovery, secure SQL querying, and an AI-driven query layer. The pipeline targets structured datasets (Spotify streaming totals) and is scoped to bridge natural language querying with strict security boundaries.

**Sandbox note:** Several AWS services required by this capstone are blocked at the IAM policy level in the provided sandbox account (`Whiz_User_353696.89077867`). These blocks are explicit `Deny` statements in a policy called `tier_1_fullaccess_policy_1_353696.89077867`, which also prevents inspecting the user's own permissions (`iam:GetUser`, `iam:ListUserPolicies` are denied). This is a sandbox-tier restriction, not a bug in the pipeline code. Details and exact error messages are in Section 4.

## 2. Architecture & Implementation Status

### Fully implemented and verified with real output

- **S3 storage** (`s3.py`): Creates a bucket via Boto3 and uploads `data.csv` under `structured-data/`. Verified via script output and AWS Console. *(Only CSV upload is implemented — PDF and JSON upload paths are not yet built.)*
- **SQL validation layer** (`sql_validator.py`, Step 2.75): Pre-execution SELECT-only validator. Tested against 5 cases including a stacked-query attempt (`SELECT ...; DELETE ...;`). All 5 cases pass as expected.
- **Sentence Transformers embeddings** (`scripts/generate_embeddings.py`): Real, local embedding generation using `all-MiniLM-L6-v2` — no Bedrock, no API key. Processed all 8,058 rows of `data.csv`, chunked lyrics into 25,665 chunks, and embedded all of them (~10 min on CPU, batched encoding). Includes a working local semantic search function (cosine similarity) as a substitute for OpenSearch, verified with real test queries returning genuinely relevant results (e.g. a "dancing and love" query correctly surfaced Taylor Swift, Bastille, and Dan + Shay lyrics about exactly that).
- **Matplotlib charts** (`scripts/generate_charts.py`): 3 charts generated directly from `data.csv` (top artists by streams, weeks-on-chart distribution, total vs. peak streams scatter) — substitute for Redshift-sourced charts since Redshift was not provisioned (see cost note below). Verified via successful script run, PNGs saved to `./charts/`.
- **Manual Glue Catalog registration** (`scripts/test_glue_manual_catalog.py`): Real database (`capstone_spotify_db`) and table (`spotify_streaming_data`) created via `glue.create_database()`/`glue.create_table()`, with all 10 real columns from `data.csv` registered and verified via `glue.get_table()`. Uses `OpenCSVSerDe` to correctly handle the quoted commas in the `lyrics` column.
- **Rule-based query router with real differentiated output** (`scripts/query_router_rulebased.py`): Replaces the earlier mock, which returned identical hardcoded SQL for every question regardless of content. Now genuinely produces different, relevant SQL per question (top-N, artist filter, average, threshold filters). Both required harder synthesis queries are implemented with dedicated handlers and produce real, honest combined answers:
  - **Churn query**: correctly routes to BOTH, pulls the real 5% churn target from the policy document, and honestly reports that no churn data exists in the ingested dataset rather than fabricating a number — framed correctly as a data gap, not a policy violation.
  - **Metadata query**: correctly routes to BOTH, makes a live `boto3` call against the real Glue Catalog table, compares its actual columns against the policy's 5 required governance fields, and correctly reports all 5 are missing.
  
  This is still rule-based/template logic rather than an LLM call (Bedrock remains blocked — see below), and is documented here as the interim substitute for the AI query layer, not a claim that it satisfies the "using Bedrock (Claude)" requirement.

- **Automated Lambda + Textract pipeline** (`scripts/lambda_function.py`, `scripts/deploy_lambda.py`): A fully real, end-to-end automated pipeline, not a manual test:
  1. A PDF uploaded to `s3://unit3capstoneac/raw-pdfs/` automatically triggers a Lambda function (`capstone-pdf-textract-processor`) via an S3 event notification — no manual invocation.
  2. The function calls Amazon Textract to extract text from the PDF.
  3. Text is chunked (500-1000 token range).
  4. The result is written back to `s3://unit3capstoneac/processed-text/<doc-id>.json` automatically.

  Verified with a real test upload: `test-upload2.pdf` → `processed-text/test-upload2.json` appeared automatically within ~10 seconds, containing correctly extracted and chunked text (1,191 characters, 2 chunks), matching the source PDF exactly.

  **This also resolves the RDS "store raw extracted text" requirement gap.** RDS was ruled out on cost, DynamoDB was blocked by IAM (`dynamodb:ListTables` denied) — storing extracted text as structured JSON in S3, a service already confirmed reliable throughout this project, closes that gap using real automation rather than a manual workaround.

  **IAM path to get here, documented for transparency:** the Lambda execution role required manual creation (`scripts/test_create_lambda_role.py`) since none of the sandbox's 10 pre-existing IAM roles had a trust policy allowing Lambda to assume them (they are all AWS service-linked roles for other services). Broad managed policies (`AmazonTextractFullAccess`) were denied when attaching to the new role, but narrow, custom-scoped inline policies (specific Textract actions; `s3:PutObject` limited to the `processed-text/` prefix only) succeeded. This confirms the sandbox's restriction pattern generalizes beyond the original three blocks: broad/managed permissions are often denied where narrow, purpose-built ones are allowed.

### Not real AWS calls (mocked, superseded by the rule-based router above)

- **Query routing & NL-to-SQL** (`query_router_final.py`, `gold.py`): The routing logic is real Python (keyword-based in `gold.py`; JSON-based intent mock in `query_router_final.py`), but neither calls Bedrock. `query_router_final.py` uses a function explicitly named `mock_invoke_bedrock()` that returns hardcoded text and fake token counts. `gold.py`'s LangGraph-style classifier routes on simple substring matching (`if "stream" in question`), not an LLM call.
- **Tokenomics tracking** (Step 2.9): The logging and cost-summary code works and produces a real report format, but the token counts it logs are synthetic (`len(prompt.split()) * 2`), not usage from an actual Bedrock response, because no real Bedrock call has succeeded yet.
- **Harder synthesis queries**: Not actually solved. In the 10-query test run, every question — including "What is our current customer churn rate?" and "Summarize the data governance policy requirements" — is routed to REDSHIFT and returns the identical hardcoded SQL (`SELECT "artist name", SUM(total)... LIMIT 3`), regardless of the question's actual content. The two required harder queries have not been answered correctly, and no evidence of citing both sources exists yet.

### Blocked by sandbox permissions — worked around with a real substitute

- **AWS Glue Crawler → manual Glue Catalog registration**: `glue:CreateCrawler` is explicitly denied in this sandbox (see Section 4), so schema auto-discovery via Crawler is not possible. However, a permission probe (`scripts/permission_probe.py`) confirmed that `glue:GetDatabases` and `glue:GetCrawlers` are allowed, meaning Glue itself is not fully blocked — only crawler creation specifically. `scripts/test_glue_manual_catalog.py` tests and confirms that `glue:CreateDatabase` and `glue:CreateTable` are both permitted, so the CSV schema was registered manually instead of via auto-discovery:
  - Database: `capstone_spotify_db`
  - Table: `spotify_streaming_data`
  - All 10 columns from `data.csv` registered and verified via `glue.get_table()`
  - Uses `OpenCSVSerDe` (not the default `LazySimpleSerDe`) because the `lyrics` column contains embedded commas and quoted text that simple delimiter parsing would misread

  This is a real, verified AWS Glue Catalog entry — not mocked — and satisfies the spirit of "catalog and discover schemas" via manual definition rather than automated discovery. Documented here as a deliberate substitution for the blocked Crawler action, not a workaround that avoids AWS entirely.

- **DynamoDB (attempted as RDS substitute)**: `dynamodb:ListTables` is also explicitly denied in this sandbox, so a DynamoDB-based substitute for RDS's "store raw extracted text" role (`scripts/dynamodb_storage.py`) could not be tested end-to-end. Given that Glue's write actions (`CreateDatabase`/`CreateTable`) succeeded while DynamoDB's read action (`ListTables`) failed, the sandbox's allow-list does not follow a simple "reads allowed, writes blocked" pattern — it is a specific, narrow list of denied actions rather than a broad category restriction. A local or alternative substitute for the RDS role is still needed.

- **Amazon Bedrock / Claude invocation** (`bedrock.py`, `query_router.py`): Bedrock's control-plane actions (`bedrock:ListFoundationModels`) are allowed, but `bedrock:InvokeModel` is denied due to a missing AWS Marketplace subscription entitlement (`aws-marketplace:ViewSubscriptions`, `aws-marketplace:Subscribe`), which this sandbox user cannot self-grant. No real call to `bedrock.invoke_model()` has returned a successful response in this environment. `bedrock.py` uses the correct inference-profile ARN pattern but its output has not been confirmed to work. `query_router.py` still uses a bare model ID (`anthropic.claude-3-haiku-20240307-v1:0`) rather than the required inference-profile ARN, so even if the Marketplace block were lifted, this specific file would need that fix too before it could work.

### Not yet started

- Lambda triggers on S3 upload
- Textract PDF extraction and chunking
- Sentence Transformers embedding generation (this does **not** require Bedrock or any blocked AWS service — it runs locally via the `sentence-transformers` Python package and needs no additional AWS permissions)
- RDS storage of raw text
- OpenSearch vector indexing and semantic retrieval
- Glue ETL jobs (normalization, validation, load into Redshift)
- Redshift as consolidated warehouse
- Matplotlib charts (2+) from Redshift data
- PDF and JSON ingestion to S3

## 3. Honest Bronze Checklist Status

| Requirement | Status |
|---|---|
| S3 stores raw PDFs, CSVs, JSONs | Partial — CSV and PDF confirmed working; JSON not tested |
| Lambda triggers on upload; Textract for PDFs | **Done** — real S3 event trigger confirmed working end-to-end |
| Textract extracts/chunks PDF text | **Done** — verified via real automated run, correct output |
| Sentence Transformers embeddings | **Done** — 8,058 rows, 25,665 chunks, verified working semantic search |
| Raw text in RDS; embeddings in OpenSearch | **Done (substituted)** — raw text stored as JSON in S3 via the automated Lambda pipeline (RDS ruled out on cost, DynamoDB blocked by IAM); embeddings stored locally as a substitute for OpenSearch, not yet indexed in real OpenSearch |
| Glue Crawler catalogs schemas | **Done (substituted)** — Crawler action blocked, manual `CreateDatabase`/`CreateTable` registration confirmed working instead |
| Glue ETL loads to Redshift | Not started |
| Redshift consolidates data | Not started |
| Matplotlib charts (2+) | **Done** — 3 charts generated from real data |
| Lambda/Boto3 automation | **Done** — real Lambda function deployed and triggered automatically via Boto3-provisioned S3 event notification |
| IAM best practices | Partial — role created with least-privilege, narrowly-scoped inline policies rather than broad managed ones (see Lambda section above) |
| AI query layer via real Bedrock calls | Blocked — Marketplace subscription permission denied; rule-based substitute implemented instead (see below) |
| SQL validation layer (5+ cases incl. stacked query) | **Done** |
| Tokenomics logging across real Bedrock calls | Logging mechanism works, but logs synthetic data since no real Bedrock call has succeeded |
| Both harder synthesis queries answered, citing both sources | **Done** — both queries correctly route to BOTH and produce real, honest combined answers (see above); implemented via rule-based handlers, not Bedrock, since Bedrock remains blocked |

## 4. Sandbox Permission Errors (Exact Messages)

**Glue Crawler creation**, attempting to catalog `s3://unit3-capstone-project-AC/structured-data/`:
```
User: arn:aws:iam::658279639631:user/Whiz_User_353696.89077867 is not authorized to
perform: glue:CreateCrawler on resource:
arn:aws:glue:us-east-1:658279639631:crawler/spotify-csv-crawler because no
identity-based policy allows the glue:CreateCrawler action
```

**Bedrock model invocation**, attempting `bedrock.invoke_model()` for Claude:
```
AccessDeniedException: Model access is denied due to IAM user or service role is not
authorized to perform the required AWS Marketplace actions
(aws-marketplace:ViewSubscriptions, aws-marketplace:Subscribe) to enable access to
this model.
```

**DynamoDB table listing**, attempting `dynamodb.list_tables()` as part of testing an RDS substitute:
```
AccessDeniedException: User: arn:aws:iam::658279639631:user/Whiz_User_353696.89077867
is not authorized to perform: dynamodb:ListTables on resource:
arn:aws:dynamodb:us-east-1:658279639631:table/* because no identity-based policy
allows the dynamodb:ListTables action
```

**IAM self-inspection**, attempting `iam:GetUser` / `iam:ListUserPolicies` / `iam:SimulatePrincipalPolicy`:
```
AccessDenied: ...with an explicit deny in an identity-based policy:
arn:aws:iam::658279639631:policy/tier_1_fullaccess_policy_1_353696.89077867
```

### Full permission map

Rather than discover blocks one at a time, `scripts/permission_probe.py` was run to test a read-only call against every service the capstone needs. Result: **11 of 14 allowed, 3 denied** (DynamoDB ListTables, IAM GetUser, IAM ListUserPolicies). Notably, read/describe/list-level access is allowed across Glue, RDS, Bedrock, Lambda, Redshift, OpenSearch, and Textract — the sandbox's restriction is a **narrow, specific denylist of individual actions**, not a broad per-service or read/write category block. This was confirmed further when `glue:CreateDatabase` and `glue:CreateTable` (write actions) succeeded despite `glue:CreateCrawler` (also a write action, same service) being denied — there is no simple pattern predicting which specific actions are blocked without testing each one directly.

**Resolution status:** Glue Crawler creation is resolved via the manual catalog substitute above. Bedrock model invocation and DynamoDB access remain unresolved and require escalation — they cannot be fixed or worked around from within the sandbox as currently provisioned, since the specific blocked actions have no available substitute API within their own services.

## 6. Gold Stretch Goals — Honest Status

**LangGraph Routing Refactor — Done.** The original `gold.py` had the right state-machine shape (classifier → conditional routing → SQL generation/validation or document search) but still called the old hardcoded SQL generator, so every REDSHIFT-routed question returned identical SQL regardless of content — the same flaw the mocked router had. `scripts/langgraph_router.py` fixes this by wiring the state machine to the real per-question logic from `query_router_rulebased.py`. Verified against 5 test questions, including both harder synthesis queries, all producing correct, differentiated output. One classifier bug was found and fixed during testing: a naive substring match on "rate" was matching inside the word "strategy" (st-**rate**-gy), causing "What does our data retention strategy state?" to misroute to BOTH instead of OPENSEARCH. Fixed with a word-boundary regex.

**Enterprise Knowledge API Gateway — Not achievable in this sandbox; two independent approaches confirmed blocked.** The original `gold.py`'s `lambda_api_handler()` was a local Python function called directly within the same script — it never touched AWS and did not satisfy "an API Gateway + Lambda endpoint... for programmatic access" as written. Two real attempts were made to fix this properly:

1. **Real API Gateway** (`scripts/deploy_api.py`): `apigateway:POST` is explicitly denied — the same block pattern seen throughout this project (Glue Crawler, Bedrock invoke, DynamoDB creation). API Gateway cannot be provisioned in this sandbox at all.
2. **Lambda Function URLs** (`scripts/deploy_api_function_url.py`), a native Lambda feature that provides a public HTTPS endpoint without API Gateway: this one is more subtle. The Function URL **was successfully created** with `AuthType: NONE`, and the resource-based permission for anonymous invocation was correctly attached and verified via `aws lambda get-policy` — both configs were confirmed correct. Yet every invocation attempt returns `403 Forbidden`, including a properly SigV4-signed IAM-authenticated request (`scripts/test_function_url_iam_auth.py`), which ruled out an auth-configuration mistake. This points to an account-level guardrail (most likely a Service Control Policy) blocking Function URL invocation entirely, regardless of auth type or IAM signing — the resource can be created, but never actually called.

The underlying query logic this endpoint would have exposed is real and fully working (see `query_router_rulebased.py` and `langgraph_router.py` above) — only the "expose it as a live network endpoint" step is blocked, and it is blocked via two independent AWS mechanisms, not one. This is documented as a confirmed sandbox limitation with concrete evidence from both attempts, not a skipped or abandoned requirement.

**Result: 1 of 2 Gold-tier stretch goals achieved for real (LangGraph); the second (Enterprise API) is genuinely blocked in this sandbox with evidence from two independent attempts, and should be added to the same instructor escalation as the Bedrock, DynamoDB, and API Gateway blocks.**

## 7. Path Forward

1. **Done:** Glue schema cataloging resolved via manual `CreateDatabase`/`CreateTable`, confirmed working against real AWS.
2. Escalate to instructor/course administrator with the exact errors in Section 4 (Bedrock InvokeModel, DynamoDB ListTables, IAM introspection), plus the full permission map from `scripts/permission_probe.py`, requesting either a permissions update or guidance on an alternative path for the remaining Bronze items.
3. Find a substitute for RDS's "store raw extracted text" role that doesn't depend on DynamoDB, since that path is also blocked — likely a local store (SQLite) or storing extracted text back in S3 as JSON, documented clearly as a substitution.
4. Implement Sentence Transformers embeddings locally — this requires no AWS permissions at all and is a real, gradeable win independent of any escalation.
5. Fix the inference-profile ARN inconsistency in `query_router.py` so that if/when Bedrock access is restored, the code is not blocked by a second, self-inflicted issue.
6. Rework routing logic so the two required harder synthesis queries are actually distinguished from simple structured queries, rather than all queries resolving to the same hardcoded SQL.
7. Once Bedrock access is confirmed working via a standalone `bedrock.py` test, replace the mocked routing/SQL-generation/tokenomics logic with real calls before re-running the 10-query test and the synthesis-query tests.
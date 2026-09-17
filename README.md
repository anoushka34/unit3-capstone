# Unit 3 Capstone: Intelligent Document Search & Pipeline Architecture

## 1. Project Overview
This project designs and builds an intelligent document search and analytics pipeline integrating cloud storage, automated schema discovery, secure querying, and an AI-driven query layer. The pipeline processes structured datasets (such as Spotify global chart totals and lyrics) and bridges natural language processing with strict security boundaries.

---

## 2. Architecture & Implementation Summary

### Successfully Implemented & Verified Components
* **Central Storage (Amazon S3):**
  * Created a custom S3 bucket (`unit3-capstone-project-AC`) via Boto3 and uploaded the primary structured dataset (`data.csv`) under the `structured-data/` prefix. Verified through both Python scripts and the AWS Web Console.
* **AI Query Backbone & Routing Logic:**
  * Configured Amazon Bedrock connectivity and built an intelligent query router that classifies natural language questions into operational intents (`REDSHIFT`, `OPENSEARCH`, `BOTH`) and dynamically generates corresponding SQL queries.
* **Mandatory SQL Validation Layer (Step 2.75):**
  * Implemented a robust pre-execution security parser that screens all generated SQL. Tested across a rigorous 5-case test suite including stacked-query attempts, successfully blocking all destructive mutations (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `GRANT`, `REVOKE`) while permitting strictly `SELECT` operations.
* **Tokenomics Tracking & Cost Summary (Step 2.9):**
  * Integrated a real-time logging middleware that records input and output token consumption across multi-step LLM operations (classification and SQL generation), producing an automated cost breakdown over a 10-query test run.

---

## 3. Encountered Roadblocks & Sandbox Constraints

Due to strict administrative permission boundaries and structural gaps within the provided AWS sandbox environment, several advanced cloud infrastructure components could not be provisioned through standard user credentials. These constraints were handled via code-driven simulation layers and documented gracefully:

### A. AWS Glue Crawler Creation Failure (IAM Permission Restriction)
* **Attempted Action:** Creating an AWS Glue Crawler (`spotify-csv-crawler`) via the AWS Console to catalog `s3://unit3-capstone-project-AC/structured-data/`.
* **Error Encountered:**
  ```text
  User: arn:aws:iam::658279639631:user/Whiz_User_353696.89077867 is not authorized to perform: glue:CreateCrawler
  because no identity-based policy allows the glue:CreateCrawler action.

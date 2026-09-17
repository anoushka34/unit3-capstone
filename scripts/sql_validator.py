# List of blocked destructive keywords
BLOCKED_KEYWORDS = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "GRANT", "REVOKE"]

def validate_sql(query: str) -> dict:
    query_upper = query.upper().strip()
   
    # Check for blocked keywords as separate words or start of query
    for keyword in BLOCKED_KEYWORDS:
        if f" {keyword} " in f" {query_upper} " or query_upper.startswith(keyword):
            return {"valid": False, "reason": f"Blocked: {keyword} not permitted"}
           
    # Ensure query starts with SELECT
    if not query_upper.startswith("SELECT"):
        return {"valid": False, "reason": "Only SELECT queries are permitted"}
       
    return {"valid": True, "reason": "OK"}

# Test suite with at least 5 test cases (including stacked query attempt)
if __name__ == "__main__":
    test_cases = [
        "SELECT artist_name, SUM(total) FROM spotify GROUP BY artist_name;",
        "DROP TABLE spotify;",
        "SELECT * FROM spotify WHERE PkStreams > 1000000; DELETE FROM spotify;", # Stacked query attempt
        "UPDATE spotify SET total = 0 WHERE artist_name = 'Drake';",
        "SELECT song_name FROM spotify ORDER BY total DESC LIMIT 5;"
    ]
   
    print("Running SQL Validation Test Suite...\n")
    for i, query in enumerate(test_cases, 1):
        result = validate_sql(query)
        print(f"Test {i}: {query}")
        print(f"Result -> Valid: {result['valid']} | Reason: {result['reason']}\n")

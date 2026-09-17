import boto3
import json

# Initialize Bedrock client
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
account_id = boto3.client("sts").get_caller_identity()["Account"]

# Mandatory inference-profile ARN pattern for Claude models on Bedrock
MODEL_ID = f"arn:aws:bedrock:us-east-1:{account_id}:inference-profile/us.anthropic.claude-sonnet-4-6"

def invoke_claude(prompt: str, max_tokens: int = 500) -> dict:
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}]
    }
    response = bedrock.invoke_model(modelId=MODEL_ID, body=json.dumps(body))
    result = json.loads(response["body"].read())
    return {
        "text": result["content"][0]["text"],
        "input_tokens": result["usage"]["input_tokens"],
        "output_tokens": result["usage"]["output_tokens"]
    }

if __name__ == "__main__":
    print("Testing Bedrock connection with Claude...")
    try:
        res = invoke_claude("Say hello and confirm you are ready for the capstone query layer.")
        print("\nResponse from Claude:")
        print(res["text"])
        print(f"\nToken usage - Input: {res['input_tokens']}, Output: {res['output_tokens']}")
    except Exception as e:
        print(f"Error connecting to Bedrock: {e}")

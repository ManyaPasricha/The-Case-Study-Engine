
import requests
import json

# ==========================================
# OLLAMA CONFIGURATION
# ==========================================

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen2.5:3b"


# ==========================================
# JSON OUTPUT NORMALIZATION
# ==========================================

def normalize_llm_output(data):

    required_fields = [
        "project_objective",
        "technology_used",
        "measured_results",
        "business_value"
    ]

    missing_information = []

    for field in required_fields:

        value = data.get(field)

        if not isinstance(value, str) or not value.strip():
            data[field] = "NOT PROVIDED"

        elif value.strip().lower() in [
            "not provided",
            "not available",
            "unknown",
            "n/a",
            "none"
        ]:
            data[field] = "NOT PROVIDED"

        else:
            data[field] = value.strip()

        if data[field] == "NOT PROVIDED":
            missing_information.append(field)

    data["missing_information"] = missing_information

    return data


# ==========================================
# JSON PARSER
# ==========================================

def parse_llm_json(content):

    if not content or not content.strip():
        raise ValueError("Ollama returned an empty response.")

    try:
        result = json.loads(content)

    except json.JSONDecodeError:

        decoder = json.JSONDecoder()
        result = None

        for position, character in enumerate(content):

            if character == "{":

                try:
                    result, _ = decoder.raw_decode(
                        content[position:]
                    )
                    break

                except json.JSONDecodeError:
                    continue

        if result is None:
            raise ValueError(
                "Ollama returned malformed or incomplete JSON."
            )

    if not isinstance(result, dict):
        raise ValueError("LLM response must be a JSON object.")

    return result


# ==========================================
# REUSABLE LLM CLIENT
# ==========================================

def ask_llm(system_prompt, user_prompt, normalize=False):

    payload = {

        "model": MODEL_NAME,

        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],

        "stream": False,

        "format": "json",

        "options": {
            "temperature": 0.0,
            "num_ctx": 2048,
            "num_predict": 800
        }
    }

    last_error = None

    for attempt in range(1, 3):

        try:

            print(
                f"Sending request to Ollama (attempt {attempt}/2)...",
                flush=True
            )

            response = requests.post(
                OLLAMA_URL,
                json=payload,
                timeout=180
            )

            response.raise_for_status()

            result = response.json()

            content = result.get(
                "message", {}
            ).get("content", "")

            parsed_output = parse_llm_json(content)

            print(
                "Ollama response received successfully.",
                flush=True
            )

            if normalize:
                return normalize_llm_output(parsed_output)

            return parsed_output

        except (
            requests.exceptions.RequestException,
            ValueError,
            KeyError
        ) as error:

            last_error = error

            print(
                f"Attempt {attempt} failed: {error}",
                flush=True
            )

    raise RuntimeError(
        f"Ollama failed after 2 attempts: {last_error}"
    )


# ==========================================
# REUSABLE EVIDENCE-GROUNDED PROMPT
# ==========================================

def evidence_grounded_prompt():

    return """
    You are an evidence-grounded project analyst.

    STRICT RULES:

    1. Use ONLY information explicitly provided.
    2. Never invent facts, numbers, people or technologies.
    3. Never assume missing information.
    4. If information is unavailable, write "NOT PROVIDED".
    5. Distinguish documented facts from unknown information.
    6. Do not convert expected benefits into measured results.
    7. Do not claim causation without supporting evidence.
    8. Return valid JSON only.
    9. Use the exact requested JSON keys.
    10. Do not add explanations outside JSON.

    Every factual statement must be traceable
    to the supplied evidence.
    """


# ==========================================
# TEST THE LLM CLIENT
# ==========================================

if __name__ == "__main__":

    system_prompt = evidence_grounded_prompt()

    user_prompt = """
    INPUT:

    An industrial company deployed an AI-based
    monitoring system to improve workplace safety.

    TASK:

    Return a JSON object with these exact keys:

    {
        "project_objective": "",
        "technology_used": "",
        "measured_results": "",
        "business_value": "",
        "missing_information": []
    }

    Do not invent technologies or numerical results.
    Mark unavailable information as NOT PROVIDED.
    """

    print("\nTESTING LOCAL LLM")
    print("-" * 45)

    output = ask_llm(
        system_prompt,
        user_prompt,
        normalize=True
    )

    print(json.dumps(
        output,
        indent=4,
        ensure_ascii=False
    ))

    print("\nLLM CONNECTION SUCCESSFUL!")

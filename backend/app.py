import os
import base64
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app, origins=["*"])

# Chatbot client — text only
chat_client = Groq(api_key=os.environ.get("API_KEY"))

# Vision client — all image-based features (challenge verification + visual search)
vision_client = Groq(api_key=os.environ.get("VISION_API_KEY"))

VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

SYSTEM_PROMPT = """You are Vayora Guide, a warm, knowledgeable, and enthusiastic AI tourism companion for Vayora – a premium travel planning platform. Your personality is friendly, inspiring, and expertly informative.

Your expertise covers:
- Destination recommendations (beaches, mountains, cities, cultural sites, hidden gems)
- Best times to visit destinations worldwide
- Local cuisine, culture, traditions, and etiquette
- Travel itineraries and trip planning
- Budget tips, luxury travel, and everything in between
- Visa requirements, travel documents, and safety advisories
- Accommodation types and recommendations
- Transportation options (flights, trains, road trips)
- Adventure activities, eco-tourism, solo travel, family travel
- Packing tips and travel essentials

Guidelines:
- Be concise yet vivid — paint pictures with words
- Use relevant emojis sparingly but meaningfully
- Bold destination names or key tips using **asterisks** when helpful
- Always encourage exploration and adventure
- If asked about something outside travel/tourism, gently steer the conversation back
- Keep replies focused — avoid walls of text; use short paragraphs
- Sign off longer answers with an inspiring nudge to explore"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_json(raw):
    """Robustly extract a JSON object from a model response."""
    raw = raw.strip()
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            part = part.strip()
            if part.lower().startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                raw = part
                break
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start != -1 and end > start:
        raw = raw[start:end]
    return json.loads(raw)


def vision_request(image_base64, mime_type, prompt_text):
    """Send an image + prompt to the vision model and return raw text."""
    valid_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    if mime_type not in valid_types:
        mime_type = "image/jpeg"

    response = vision_client.chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_base64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt_text
                    }
                ]
            }
        ],
        max_tokens=1024,
        temperature=0.1,
    )
    return response.choices[0].message.content.strip()


# ── Chatbot ───────────────────────────────────────────────────────────────────

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"error": "Missing 'message' in request body"}), 400

    user_message = data["message"].strip()
    if not user_message:
        return jsonify({"error": "Message cannot be empty"}), 400

    history = data.get("history", [])
    messages = []
    for entry in history:
        role    = entry.get("role")
        content = entry.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})

    try:
        completion = chat_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            max_tokens=1024,
            temperature=0.7,
        )
        return jsonify({"reply": completion.choices[0].message.content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Challenge Verification ────────────────────────────────────────────────────

@app.route("/api/verify-challenge", methods=["POST"])
def verify_challenge():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data received"}), 400

    image_base64 = data.get("imageBase64")
    mime_type    = data.get("mimeType", "image/jpeg")
    challenge    = data.get("challengeText", "")

    if not image_base64:
        return jsonify({"error": "No image provided"}), 400
    if not challenge:
        return jsonify({"error": "No challenge text provided"}), 400

    try:
        base64.b64decode(image_base64, validate=True)
    except Exception:
        return jsonify({"error": "Invalid image data"}), 400

    prompt = (
        f'The user is trying to complete this travel challenge: "{challenge}"\n\n'
        'Look at the photo carefully and decide if it genuinely matches the challenge.\n\n'
        'Reply ONLY with a JSON object, no markdown, no extra text:\n'
        '{"approved": true, "reason": "short friendly reason"}\n'
        'or\n'
        '{"approved": false, "reason": "short friendly reason"}'
    )

    try:
        raw      = vision_request(image_base64, mime_type, prompt)
        result   = extract_json(raw)
        approved = bool(result.get("approved", False))
        reason   = result.get("reason", "Verification complete.")
        return jsonify({"approved": approved, "reason": reason})
    except json.JSONDecodeError:
        return jsonify({"approved": False, "reason": "Could not parse AI response. Please try again."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Visual Search ─────────────────────────────────────────────────────────────

@app.route("/api/visual-search", methods=["POST"])
def visual_search():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data received"}), 400

    image_base64 = data.get("imageBase64")
    mime_type    = data.get("mimeType", "image/jpeg")

    if not image_base64:
        return jsonify({"error": "No image provided"}), 400

    try:
        base64.b64decode(image_base64, validate=True)
    except Exception:
        return jsonify({"error": "Invalid image data"}), 400

    prompt = (
        'You are an expert travel guide with encyclopaedic knowledge of world destinations.\n\n'
        'Analyse this travel photo and respond with ONLY a JSON object (no markdown, no extra text) '
        'in this exact format:\n'
        '{\n'
        '  "identified": {\n'
        '    "name": "Name of the place or landmark (e.g. Santorini, Greece or Angkor Wat, Cambodia)",\n'
        '    "emoji": "single relevant emoji",\n'
        '    "description": "2-3 sentence description of what makes this place special"\n'
        '  },\n'
        '  "similar": [\n'
        '    {\n'
        '      "name": "Place Name",\n'
        '      "country": "Country Name",\n'
        '      "flag": "flag emoji",\n'
        '      "why": "One concise sentence explaining the visual or cultural similarity",\n'
        '      "match": "85%",\n'
        '      "tag": "Beach",\n'
        '      "tagColor": "#00d4b8"\n'
        '    }\n'
        '  ]\n'
        '}\n\n'
        'Choose tag from: Beach, Mountain, City, Temple, Heritage, Nature, Island, Village, Desert, Forest.\n'
        'Return exactly 6 similar destinations. Make similarities genuine — consider architecture, '
        'landscape, atmosphere, colour palette, and cultural character. '
        'Return ONLY the JSON, nothing else.'
    )

    try:
        raw    = vision_request(image_base64, mime_type, prompt)
        result = extract_json(raw)

        # Validate expected structure
        if "identified" not in result or "similar" not in result:
            raise ValueError("Unexpected response structure from AI")

        return jsonify(result)
    except json.JSONDecodeError:
        return jsonify({"error": "AI returned an unexpected format. Please try again."}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Health ────────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "Vayora Backend"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)

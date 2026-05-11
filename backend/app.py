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

# Chatbot client
chat_client = Groq(api_key=os.environ.get("API_KEY"))

# Vision client — separate key for image verification
vision_client = Groq(api_key=os.environ.get("VISION_API_KEY"))

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
        role = entry.get("role")
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
        reply = completion.choices[0].message.content
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Image Verification ────────────────────────────────────────────────────────

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

    # Ensure mime_type is a valid image type
    valid_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    if mime_type not in valid_types:
        mime_type = "image/jpeg"

    prompt = (
        f'The user is trying to complete this travel challenge: "{challenge}"\n\n'
        'Look at the photo carefully and decide if it genuinely matches the challenge.\n\n'
        'Reply ONLY with a JSON object, no markdown, no extra text:\n'
        '{"approved": true, "reason": "short friendly reason"}\n'
        'or\n'
        '{"approved": false, "reason": "short friendly reason"}'
    )

    try:
        response = vision_client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
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
                            "text": prompt
                        }
                    ]
                }
            ],
            max_tokens=256,
            temperature=0.1,
        )

        raw = response.choices[0].message.content.strip()

        # Strip markdown fences if present
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.lower().startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        # Find JSON object in response even if there's surrounding text
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start != -1 and end > start:
            raw = raw[start:end]

        result   = json.loads(raw)
        approved = bool(result.get("approved", False))
        reason   = result.get("reason", "Verification complete.")
        return jsonify({"approved": approved, "reason": reason})

    except json.JSONDecodeError:
        # If model didn't return valid JSON, default to not approved
        return jsonify({"approved": False, "reason": "Could not parse AI response. Please try again."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Health ────────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "Vayora Backend"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)

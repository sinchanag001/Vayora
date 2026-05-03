import express from 'express';
  import cors from 'cors';
  import Anthropic from '@anthropic-ai/sdk';
  import { fileURLToPath } from 'url';
  import { dirname, join } from 'path';

  const __dirname = dirname(fileURLToPath(import.meta.url));
  const app = express();
  const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

  app.use(cors());
  app.use(express.json({ limit: '20mb' }));
  app.use(express.static(__dirname)); // serves index.html

  // ── Visual Place Search ────────────────────────────────────────────────────
  app.post('/api/visual-search', async (req, res) => {
    const { imageBase64, mimeType } = req.body;
    if (!imageBase64 || !mimeType)
      return res.status(400).json({ error: 'imageBase64 and mimeType are required' });

    const prompt = 'You are an expert travel guide with encyclopaedic knowledge of world destinations.\n\nAnalyse this travel photo and respond with ONLY a JSON object (no markdown, no extra text) in this exact format:\n{\n  "identified": {\n    "name": "Name of the place or landmark (e.g. Santorini, Greece or Angkor Wat, Cambodia)",\n    "emoji": "single relevant emoji",\n    "description": "2-3 sentence description of what makes this place special"\n  },\n  "similar": [\n    {\n      "name": "Place Name",\n      "country": "Country Name",\n      "flag": "flag emoji",\n      "why": "One concise sentence explaining the visual or cultural similarity",\n      "match": "85%",\n      "tag": "Beach",\n      "tagColor": "#00d4b8"\n    }\n  ]\n}\n\nChoose tag from: Beach, Mountain, City, Temple, Heritage, Nature, Island, Village, Desert, Forest.\nReturn exactly 6 similar destinations. Make similarities genuine. Return ONLY the JSON, nothing else.';

    try {
      const message = await anthropic.messages.create({
        model: 'claude-opus-4-5',
        max_tokens: 8192,
        messages: [{ role: 'user', content: [
          { type: 'image', source: { type: 'base64', media_type: mimeType, data: imageBase64 } },
          { type: 'text', text: prompt }
        ]}]
      });
      const text = message.content.map(b => b.text ?? '').join('').trim();
      const json = text.match(/\{[\s\S]*\}/);
      res.json(JSON.parse(json ? json[0] : text));
    } catch (err) {
      console.error('visual-search error:', err.message);
      res.status(500).json({ error: err.message });
    }
  });

  // ── Challenge Proof Verification ───────────────────────────────────────────
  app.post('/api/verify-proof', async (req, res) => {
    const { imageBase64, mimeType, challengeText } = req.body;
    if (!imageBase64 || !mimeType || !challengeText)
      return res.status(400).json({ error: 'imageBase64, mimeType and challengeText are required' });

    const prompt = `You are an extremely strict travel challenge judge for Voyora. Your default is REJECT.

  THE CHALLENGE: "${challengeText}"

  DECISION PROCESS:
  1. What does the photo actually show? Describe it to yourself.
  2. What specific visual evidence would prove this challenge was completed?
  3. Does the photo contain that specific evidence? If there is ANY doubt, REJECT.

  AUTOMATIC REJECT — always reject these no matter what challenge:
  - Selfies or portraits of people without relevant background context
  - Generic travel photos (random beach, mountain, city skyline) unless the challenge specifically calls for exactly that
  - Screenshots, memes, drawings, digital art, cartoons
  - Bedroom, living room, kitchen, or other generic indoor photos
  - Pet photos, food photos without clear context matching the challenge
  - Any photo that could be from anywhere and isn't specifically linked to the challenge

  ONLY APPROVE when the photo contains unmistakable direct visual evidence of THIS specific challenge being done.

  When in doubt → REJECT.

  RESPOND with ONLY a raw JSON object, no markdown fences, no extra text whatsoever:
  {"approved": true, "reason": "One sentence describing exactly what in the photo proves the challenge"}
  or
  {"approved": false, "reason": "One sentence saying what you see and what specific photo would be valid proof"}`;

    try {
      const message = await anthropic.messages.create({
        model: 'claude-opus-4-5',
        max_tokens: 200,
        messages: [{ role: 'user', content: [
          { type: 'image', source: { type: 'base64', media_type: mimeType, data: imageBase64 } },
          { type: 'text', text: prompt }
        ]}]
      });
      const text = message.content.map(b => b.text ?? '').join('').trim();
      const json = text.match(/\{[\s\S]*"approved"[\s\S]*\}/);
      let result;
      try { result = JSON.parse(json ? json[0] : text.replace(/```json|```/g, '').trim()); }
      catch { result = { approved: false, reason: 'Could not read your photo clearly. Please try a clearer image.' }; }
      if (!result.reason) result.reason = result.approved ? 'Challenge completed!' : 'Please upload a photo that specifically shows the challenge.';
      res.json(result);
    } catch (err) {
      console.error('verify-proof error:', err.message);
      res.status(500).json({ error: err.message });
    }
  });

  const PORT = process.env.PORT || 3000;
  app.listen(PORT, () => console.log(`Voyora server running on http://localhost:${PORT}`));
  
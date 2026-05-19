# Vayora – AI Travel Planner

  An AI-powered travel planner with visual place search and challenge verification.

  ## Quick Start

  ```bash
  # 1. Install dependencies
  npm install

  # 2. Add your  API key
  cp .env.example .env
  # Edit .env and add your key 

  # 3. Run the server
  npm start
  # App opens at http://localhost:5001
  ```

  ## Features
  - 🗺 AI itinerary generator
  - 📸 Visual place search (upload a photo → find similar destinations)
  - ✅ Travel challenge verification
  - 🗣 Local phrases for 20+ countries
  - 🎒 Smart packing lists

  ## Project Structure
  ```
  index.html    ← Full frontend app (all-in-one)
  server.js     ← Express API server (AI endpoints)
  package.json  ← Dependencies
  .env          ← Your API key (never commit this!)
  ```

  ## API Endpoints
  - `POST /api/visual-search` — Identifies a travel photo and suggests similar destinations
  - `POST /api/verify-proof` — Verifies a challenge completion photo
  

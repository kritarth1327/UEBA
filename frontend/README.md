# UEBA Security Analytics Frontend

A professional security analytics dashboard for User and Entity Behavior Analytics (UEBA), built with React, Vite, Framer Motion, Recharts, and Lucide React.

## Design Philosophy

- **Restrained & Professional**: Clean, focused interface built on charcoal, slate, and warm off-white tones, avoiding distracting cyberpunk neon styling.
- **Truthful Analytics**: Strictly renders authenticated data from the backend API. All empty states honestly indicate pending ingestion or unassessed status instead of rendering fabricated telemetry.
- **Explainability First**: Breaks down detection signals into Supervised ML threat probabilities, ANN Autoencoder reconstruction loss, and baseline z-score deviations.
- **Seamless Triage**: Interactive queue with persistent alert status updates (`OPEN`, `INVESTIGATING`, `RESOLVED`, `DISMISSED`).

## Getting Started

1. Install dependencies:
   ```powershell
   npm install
   ```
2. Configure `.env` (optional, defaults to local Vite proxy at `http://127.0.0.1:8000`):
   ```powershell
   Copy-Item .env.example .env
   ```
3. Run the development server:
   ```powershell
   npm run dev
   ```
4. Build for production:
   ```powershell
   npm run build
   ```

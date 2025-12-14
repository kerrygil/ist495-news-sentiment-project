# Frontend – Stock Sentiment Dashboard

This directory contains the Next.js frontend for the Stock Sentiment Dashboard.  
It provides the UI for browsing recent articles, viewing ticker insights, and interacting with the 3D performance visualization.

---

## Requirements

- **Node.js ≥ 18** (project tested on Node 22.x)
- **npm ≥ 9**

Check your installed versions:

```bash
node --version
npm --version
```

If needed, download Node from: https://nodejs.org/en/download


## Installation
From the `frontend` directory:
```bash
npm install
```

This installs all packages listed in `package.json`, including:
- `next` (frontend-framework)
- `react` / `react-dom` (frontend library)
- `three` (3D rendering)
- `three-spritetext` (labels for 3D plot)
- `@react-three/drei` (OrbitControls helper)
- `swr` (data fetching from backend)

### Running the Frontend
Start the development server from the `frontend` directory:
```bash
npm run dev
```

Then open: 
```
http://localhost:3000
```

This connects the backend API at:
```
http://127.0.0.1:8000
```

Make sure the backend is running in a separate window.

## Project Structure 
```
frontend/
  app/
    page.tsx        → Main dashboard UI and 3D graph
  node_modules/     → Installed dependencies
  package.json      → Dependencies and scripts
```

## Notes on 3D Graph
The 3D stock performance visualization uses: 
- three.js for rendering
- OrbitControls from drei for camera navigation
- SpriteText for symbol labels
- Custom hit-testing + tooltips for point interactions

No Tailwind configuration is required beyond what ships with Next.js.

## Building for Production
From the `frontend` directory:
```bash
npm run build
npm start
```
This generates an optimized `.next` directory and starts the production server.

--- 

If you encounter module or dependency issues, ensure you run commands from the `frontend` directory and that the root project does not contain any leftover `node_modules` folder. 
# AI Data Analyst — React Frontend

A calm, precise, and evidence-first React application implementing the complete **[DESIGN.md](../docs/DESIGN.md)** specification for the **AI Data Analyst** system.

---

## 1. Architecture & Directory Map

```
frontend/
├── index.html                   # HTML entrypoint with Inter & JetBrains Mono fonts
├── vite.config.js               # Vite configuration with /api backend proxy
├── tailwind.config.js           # DESIGN.md semantic token mappings (Signal Indigo, Evidence Teal, etc.)
├── postcss.config.js            # PostCSS configuration
├── package.json                 # React 18, Vite, Lucide-React, TailwindCSS
├── src/
│   ├── main.jsx                 # React root mount
│   ├── App.jsx                  # Main screen router, global overlay coordinator
│   ├── index.css                # Tailwind directives, custom tabular-nums & dark theme tokens
│   ├── data/
│   │   └── sampleData.js        # Realistic student_performance.csv data, findings & issues
│   ├── services/
│   │   ├── api.js               # Clean REST client for FastAPI backend (/api/v1)
│   │   └── toastContext.jsx     # Auto-dismiss toast notification system (4s timer)
│   └── components/
│       ├── common/              # Core reusable UI primitives
│       │   ├── Button.jsx       # 10px rounded, 44px tall buttons (Primary, Secondary, Text)
│       │   ├── Badge.jsx        # Pill badges with text and color indicators (never color alone)
│       │   └── TopBar.jsx       # 64px header with brand, stages, theme toggle, and sign-in
│       ├── overlays/            # Modals & Slide-over Drawers
│       │   ├── NavigationDrawer.jsx # 320px slide-over history drawer
│       │   ├── AuthModal.jsx        # 440px Sign-in & Create account modal
│       │   └── CalculationModal.jsx # Evidence modal showing plain-English, math formula, & Python code
│       ├── charts/              # Interactive SVG Charts
│       │   ├── ScatterPlot.jsx  # Attendance vs Marks with OLS regression line & hover tooltips
│       │   ├── BarChart.jsx     # Department variance with 95% Confidence Interval error bars
│       │   ├── BoxPlot.jsx      # Tukey 1.5x IQR box plot with highlighted outlier rings
│       │   └── ChartSwitcher.jsx# Segmented control for chart-type switching
│       └── screens/             # The 4 Core Screens
│           ├── WelcomeScreen.jsx# Screen 1: Dropzone, sample dataset loader, trust pledge
│           ├── LoadingScreen.jsx# Screen 2: 96px circular spinner & 4-step pipeline checklist
│           ├── ReviewScreen.jsx # Screen 3: 5 summary filter tiles, issue table, sticky bottom bar
│           └── ResultsScreen.jsx# Screen 4: 3-column results workbench (Files, Findings, Chat)
```

---

## 2. Screen Flow Implementation

1. **Screen 1: Welcome and Upload** (`WelcomeScreen.jsx`)
   - Large dashed drag-and-drop drop zone (up to 10 MB, CSV only).
   - "Try a sample dataset" button loading `student_performance.csv` (1,200 rows, 184 KB).
   - Compact file chip with row count, column count, size, and remove action.
   - Prominent wide "Enter Workbench" button.
   - Trust pledge: *"Calculations run in code, not guessed. Your file can be deleted anytime."*

2. **Screen 2: Loading State** (`LoadingScreen.jsx`)
   - 96px circular progress ring with live numeric percentage telemetry.
   - 4-step execution audit checklist (Reading file, Detecting types, Checking missing/duplicates, Checking outliers).
   - Cancel button to abort and return to Screen 1.

3. **Screen 3: Data Health Review** (`ReviewScreen.jsx`)
   - Step indicator: `1 Upload > 2 Review > 3 Results`.
   - 5 clickable summary filter cards (Columns, Missing values, Duplicates, Outliers, Data range).
   - High-density issue table with checkboxes, severity chips (High, Medium, Low), and expandable "Why?" algorithmic justifications.
   - Sticky bottom action bar: *"N fixes selected. Your original file stays unchanged."* and large primary **Analyse** button.

4. **Screen 4: Results Dashboard** (`ResultsScreen.jsx`)
   - 3-column desktop layout (responsive to mobile/tablet):
     - **Left Column (260px)**: "Data Workbench" — Export cleaned CSV, Download executive report (PDF/HTML), "What changed" collapsible audit trail, and deterministic hash certification.
     - **Center Column (Fluid)**: "Key findings" — Ranked by effect size, interactive charts with switcher, hover tooltips, and Evidence Teal *"See how this was calculated"* link.
     - **Right Column (360px)**: "Ask a follow-up" — Follow-up conversational chat with suggested query chips, assistant answers with calculation citation links.

---

## 3. Running and Building

### Development Server
```bash
cd frontend
npm run dev
```
The application runs on `http://localhost:5173` and proxies `/api` calls directly to the FastAPI backend at `http://localhost:8000`.

### Production Build
```bash
cd frontend
npm run build
```
Generates production-optimized static assets in `frontend/dist/`.


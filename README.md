# ML-Powered Compiler Optimization Advisor

**Undergraduate Assignment — Principles of Compiler Design (PCD)**

A complete compiler pipeline for a restricted C-like language with a genuinely trained ML model that recommends and gates optimization passes.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12 + Flask 3.0 |
| Compiler | PLY (Python Lex-Yacc) 3.11 |
| ML | Scikit-learn 1.5 |
| Frontend | HTML5 + Vanilla CSS + JavaScript |
| Visualization | Chart.js |

---

## Project Structure

```
PCD_Assignment/
├── backend/
│   ├── app.py              ← Flask entry point
│   ├── config.py           ← All configuration & constants
│   ├── requirements.txt
│   ├── compiler/           ← 8 compiler phase modules (PLY-based)
│   ├── ml/                 ← Feature extractor, dataset gen, trainer, model
│   ├── api/                ← Flask blueprints + pipeline orchestrator
│   └── tests/              ← Unit tests for every module
├── frontend/               ← HTML/CSS/JS dashboard
└── docs/                   ← Grammar, API reference, dataset design
```

---

## Setup Instructions

### 1. Create and activate a virtual environment
```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the Flask development server
```bash
python app.py
```

### 4. Open the dashboard
Visit `http://localhost:5000` in your browser,
or open `frontend/index.html` directly.

---

## Supported Optimizations

| Pass | What it Does |
|---|---|
| Constant Folding | `2 + 3` → `5` at compile time |
| Constant Propagation | Replace variable uses with known constant values |
| Common Subexpression Elimination | Reuse already-computed subexpressions |
| Dead Code Elimination | Remove assignments whose results are never used |
| Strength Reduction | `x * 4` → `x << 2` (cheaper operations) |

> **ML-Gated**: Only passes the trained model recommends (confidence ≥ 0.5) are applied.

---

## ML Model

- **Type**: `MultiOutputClassifier(RandomForestClassifier)`
- **Features**: 15 structural features extracted from AST + TAC
- **Labels**: 5 binary labels (one per optimization pass)
- **Dataset**: ~600 synthetic programs, 80/20 train/test split
- **Labels derived automatically** by checking whether each pass reduces instruction count
- **Evaluation**: Hamming Loss, per-label F1, Precision/Recall (on unseen 20% test set)

---

## Development Phases

| Phase | Status |
|---|---|
| 0 — Project Setup | ✅ Complete |
| 1 — Lexer | ⬜ Pending |
| 2 — Parser + AST | ⬜ Pending |
| 3 — Semantic Analysis | ⬜ Pending |
| 4 — IR Generation (TAC) | ⬜ Pending |
| 5 — Optimization Passes | ⬜ Pending |
| 6 — Feature Extractor | ⬜ Pending |
| 7 — Dataset + Model Training | ⬜ Pending |
| 8 — ML Model Interface | ⬜ Pending |
| 9 — Pipeline + API | ⬜ Pending |
| 10 — Frontend Dashboard | ⬜ Pending |
| 11 — Integration Tests | ⬜ Pending |
| 12 — Viva Prep | ⬜ Pending |

---

## Running Tests

```bash
cd backend
python -m pytest tests/ -v
```

---

## API Endpoints

| Method | Route | Description |
|---|---|---|
| GET | `/api/health` | Server liveness check |
| POST | `/api/analyze` | Full pipeline: tokens → AST → TAC → ML recommendations |
| POST | `/api/optimize` | Apply ML-recommended passes, return before/after TAC |

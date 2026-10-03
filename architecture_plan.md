# ML-Powered Compiler Optimization Advisor — Architecture & Development Plan

> **Status**: Awaiting Approval before Implementation  
> **Assignment**: Principles of Compiler Design (PCD) — Undergraduate Project

---

## 1. Project Overview

This system accepts source code written in a **restricted C-like language**, processes it through all major compiler phases, extracts structural features from the code, and feeds those features into a **genuinely trained ML model** to recommend and apply optimizations. The entire pipeline is exposed via an interactive web dashboard.

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         WEB FRONTEND (Browser)                      │
│   HTML + CSS + JavaScript + Chart.js                                │
│   Code Editor → Phase-by-Phase Visualization → ML Recommendations  │
└───────────────────────────┬─────────────────────────────────────────┘
                            │  HTTP (REST API)
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         FLASK API SERVER                            │
│   /api/analyze     /api/optimize     /api/explain                   │
└───┬──────────────────────────────────────────────────────────┬──────┘
    │                                                          │
    ▼                                                          ▼
┌───────────────────────────┐              ┌───────────────────────────┐
│     COMPILER ENGINE       │              │      ML ADVISOR ENGINE    │
│  (compiler/  package)     │              │  (ml/  package)           │
│                           │              │                           │
│  1. Lexer (PLY)           │  ──features─▶│  Feature Extractor        │
│  2. Parser (PLY)          │              │  Trained Model (sklearn)  │
│  3. AST Builder           │◀──recs──────│  Recommendation Generator │
│  4. Semantic Analyzer     │              │  Confidence Scores        │
│  5. IR Generator (TAC)    │              └───────────────────────────┘
│  6. Optimizer (passes)    │
│  7. Optimized IR          │
└───────────────────────────┘
```

### Data Flow (Single Request)

```
Source Code (string)
        │
        ▼
[Lexer] → Token Stream
        │
        ▼
[Parser] → Concrete Syntax + Error Report
        │
        ▼
[AST Builder] → AST (nested dict / node objects)
        │
        ▼
[Semantic Analyzer] → Symbol Table + Type Errors
        │
        ▼
[IR Generator] → Three-Address Code (TAC) List
        │
        ├──────────────────────────────────────────┐
        ▼                                          ▼
[Feature Extractor]                        [Traditional Optimizer]
        │                                          │
        ▼                                          ▼
[ML Model] → Recommended Optimizations     [Optimized TAC List]
        │
        ▼
[API Response] → JSON (tokens, AST, TAC, features,
                        recommendations, before/after comparison)
```

---

## 3. Modular Folder Structure

```
PCD_Assignment/
│
├── backend/
│   ├── app.py                        ← Flask entry point
│   ├── config.py                     ← Config (debug, CORS, paths)
│   ├── requirements.txt
│   │
│   ├── compiler/                     ← Compiler Engine Package
│   │   ├── __init__.py
│   │   ├── lexer.py                  ← PLY Lexer (tokenizer)
│   │   ├── parser.py                 ← PLY Parser (grammar rules)
│   │   ├── ast_nodes.py              ← AST Node class definitions
│   │   ├── ast_builder.py            ← Builds AST from parse tree
│   │   ├── semantic_analyzer.py      ← Type checking, symbol table
│   │   ├── symbol_table.py           ← Symbol Table implementation
│   │   ├── ir_generator.py           ← TAC (Three-Address Code) gen
│   │   ├── optimizer.py              ← Traditional optimization passes
│   │   └── grammar.txt               ← BNF grammar reference doc
│   │
│   ├── ml/                           ← ML Advisor Package
│   │   ├── __init__.py
│   │   ├── feature_extractor.py      ← Extracts numeric features from AST/TAC
│   │   ├── trainer.py                ← Model training script
│   │   ├── model.py                  ← Model load/predict interface
│   │   ├── recommendation.py         ← Maps model output → human explanations
│   │   ├── data/
│   │   │   ├── generate_dataset.py   ← Synthetic dataset generator
│   │   │   └── dataset.csv           ← Generated training data
│   │   └── saved_models/
│   │       └── optimizer_model.pkl   ← Serialized trained model
│   │
│   ├── api/                          ← Flask Blueprints (REST API)
│   │   ├── __init__.py
│   │   ├── analyze.py                ← POST /api/analyze
│   │   ├── optimize.py               ← POST /api/optimize
│   │   └── health.py                 ← GET  /api/health
│   │
│   └── tests/                        ← Unit Tests
│       ├── test_lexer.py
│       ├── test_parser.py
│       ├── test_semantic.py
│       ├── test_ir.py
│       ├── test_optimizer.py
│       └── test_ml.py
│
├── frontend/
│   ├── index.html                    ← Single-page dashboard
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   ├── main.js                   ← App entry, event wiring
│   │   ├── editor.js                 ← Code editor (CodeMirror or textarea)
│   │   ├── api.js                    ← Fetch wrapper for Flask API
│   │   ├── visualizer.js             ← AST tree rendering
│   │   ├── charts.js                 ← Chart.js graphs
│   │   └── phases.js                 ← Renders each compiler phase panel
│   └── assets/
│       └── icons/
│
├── docs/
│   ├── grammar.md                    ← Formal grammar specification
│   ├── dataset_design.md             ← Dataset feature descriptions
│   ├── ml_model.md                   ← Model selection rationale
│   └── api_reference.md              ← REST API docs
│
└── README.md
```

---

## 4. Role of Each Module

### 4.1 Compiler Engine (`compiler/`)

| Module | Role |
|---|---|
| `lexer.py` | Tokenizes source using PLY. Defines tokens: keywords, identifiers, literals, operators, delimiters. |
| `parser.py` | Defines BNF grammar rules for PLY. Builds parse tree. Reports syntax errors with line numbers. |
| `ast_nodes.py` | Defines typed Python classes for each AST node (`ProgramNode`, `FuncDefNode`, `ForLoopNode`, `AssignNode`, `BinOpNode`, etc.) |
| `ast_builder.py` | Walks the parse tree and constructs structured AST node objects. |
| `semantic_analyzer.py` | Performs type checking, undeclared variable detection, type mismatch detection, and populates the symbol table. |
| `symbol_table.py` | Implements scoped symbol tables (stack-based), tracking variable names, types, and scopes. |
| `ir_generator.py` | Traverses the AST and emits Three-Address Code instructions (`t1 = a + b`, `if t1 goto L1`, etc.) |
| `optimizer.py` | Applies classical optimization passes over the TAC. |

### 4.2 ML Advisor (`ml/`)

| Module | Role |
|---|---|
| `feature_extractor.py` | Extracts ~20 numeric features from AST + TAC (e.g., loop count, temp variable count, operation frequencies). |
| `generate_dataset.py` | Programmatically generates hundreds of synthetic C-like programs, runs them through the compiler, extracts features, and labels the dataset. |
| `trainer.py` | Loads dataset, trains a `RandomForestClassifier` (multi-label), evaluates accuracy, serializes model to `.pkl`. |
| `model.py` | Loads the saved model and exposes `predict(features)` → list of recommended optimizations. |
| `recommendation.py` | Converts model output class labels into human-readable explanation strings with descriptions and examples. |

### 4.3 Flask API (`api/`)

| Endpoint | Method | Input | Output |
|---|---|---|---|
| `/api/health` | GET | — | Server status |
| `/api/analyze` | POST | `{ "code": "..." }` | Tokens, AST, symbol table, TAC, features, ML recommendations |
| `/api/optimize` | POST | `{ "code": "..." }` | Before TAC, after TAC, applied optimizations, diff stats |

### 4.4 Frontend (`frontend/`)

| Module | Role |
|---|---|
| `editor.js` | Syntax-highlighted code input area |
| `phases.js` | Renders output of each compiler phase in tabbed panels |
| `visualizer.js` | Renders AST as an interactive tree diagram (D3.js or CSS tree) |
| `charts.js` | Chart.js bar/radar charts: instruction count before vs. after, feature importance, confidence scores |
| `api.js` | Handles all AJAX calls to Flask backend |

---

## 5. Restricted C-Like Language Specification

To keep the compiler manageable for a university project, we define a **restricted grammar** supporting only:

```
Programs:
  - Global variable declarations (int, float)
  - Function definitions (with typed parameters and return values)
  - main() function as entry point

Statements:
  - Variable declarations: int x; float y;
  - Assignments: x = expr;
  - Arithmetic expressions: +, -, *, /
  - Relational expressions: <, >, <=, >=, ==, !=
  - if / if-else blocks
  - while loops
  - for loops
  - return statements
  - Function calls (with arguments)

NOT Supported (by design):
  - Pointers, arrays, structs
  - Preprocessor directives (#include, #define)
  - String types, char types
  - Dynamic memory allocation
  - Switch statements, do-while
```

---

## 6. Traditional Optimization Passes

The `optimizer.py` module will implement these classical TAC-level optimization passes:

| Pass | Description |
|---|---|
| **Constant Folding** | Replace `t1 = 2 + 3` with `t1 = 5` at compile time |
| **Constant Propagation** | Replace uses of `x` with its constant value where known |
| **Dead Code Elimination** | Remove assignments whose result is never used |
| **Common Subexpression Elimination (CSE)** | Detect and reuse previously computed expressions |
| **Strength Reduction** | Replace `x * 2` with `x + x`, `x * 4` with `x << 2` |
| **Loop-Invariant Code Motion (LICM)** | Move expressions that don't change inside a loop to before the loop |
| **Copy Propagation** | Replace `y = x; ... use y ...` with direct use of `x` |
| **Algebraic Simplification** | Replace `x * 1 → x`, `x + 0 → x`, `x / 1 → x` |

---

## 7. ML Model Design

### 7.1 Feature Vector (~20 Features)

These are extracted from AST + TAC by `feature_extractor.py`:

| # | Feature Name | Description |
|---|---|---|
| 1 | `num_loops` | Total for/while loop count |
| 2 | `loop_depth_max` | Maximum loop nesting depth |
| 3 | `num_functions` | Number of function definitions |
| 4 | `num_assignments` | Total assignment statements |
| 5 | `num_branches` | Total if/else branch count |
| 6 | `tac_instruction_count` | Total TAC instructions |
| 7 | `temp_var_count` | Number of temporary variables in TAC |
| 8 | `const_literal_count` | Number of constant literals used |
| 9 | `add_op_count` | Number of `+` operations |
| 10 | `mul_op_count` | Number of `*` operations |
| 11 | `div_op_count` | Number of `/` operations |
| 12 | `redundant_assign_count` | Detected redundant assignments |
| 13 | `invariant_exprs_in_loops` | Count of loop-invariant subexpressions |
| 14 | `common_subexpr_count` | Count of repeated subexpressions |
| 15 | `dead_var_count` | Variables assigned but never read |
| 16 | `const_fold_opportunities` | Const-foldable expressions detected |
| 17 | `strength_reduce_opportunities` | Multiply-by-power-of-2 patterns found |
| 18 | `copy_prop_candidates` | Simple copy assignments detected |
| 19 | `has_recursion` | Boolean — function calls itself |
| 20 | `avg_block_size` | Average instructions per basic block |

### 7.2 Output Labels (Multi-Label Classification)

The model predicts a subset of:
- `CONSTANT_FOLDING`
- `CONSTANT_PROPAGATION`
- `DEAD_CODE_ELIMINATION`
- `CSE`
- `STRENGTH_REDUCTION`
- `LICM`
- `COPY_PROPAGATION`
- `ALGEBRAIC_SIMPLIFICATION`

### 7.3 Model Selection

| Model | Why Chosen |
|---|---|
| **RandomForestClassifier** (Primary) | Handles multi-label well with `MultiOutputClassifier`, interpretable feature importance, robust to noisy synthetic data |
| `MLPClassifier` (Secondary/Compare) | Neural approach, useful as a comparison |

### 7.4 Training Approach

- **Wrapper**: `sklearn.multioutput.MultiOutputClassifier`
- **Evaluation**: Hamming Loss, F1-Score (micro/macro), Accuracy per label
- **Train/Test Split**: 80/20

---

## 8. Dataset Generation Strategy

### How to Generate Labeled Training Data

The dataset is **programmatically generated** — not hand-labeled:

**Step 1 — Generate Synthetic Programs**  
`generate_dataset.py` uses templates and randomization to create hundreds of valid C-like programs with varying:
- Loop structures (nested/single/none)
- Arithmetic patterns (constants, repeated subexpressions, multiplications by powers of 2)
- Variable usage (dead variables, copy chains)

**Step 2 — Run Through Compiler**  
Each synthetic program is passed through the full compiler pipeline (lexer → parser → semantic → IR) to produce its TAC.

**Step 3 — Apply All Optimization Passes**  
Each pass is applied individually and checked — if the pass actually *reduces* instruction count or eliminates a construct, it is labeled `1` (beneficial), else `0`.

**Step 4 — Extract Feature Vector**  
The `feature_extractor.py` runs on each program's AST + TAC to produce a 20-dimensional feature vector.

**Step 5 — Save to CSV**  
Each row = `[feature_1, ..., feature_20, label_CF, label_CP, label_DCE, label_CSE, ...]`

This gives us a **genuinely labeled, structurally consistent dataset** where labels are derived from actual optimization analysis, not assumptions.

---

## 9. Technical Challenges & Solutions

| Challenge | Solution |
|---|---|
| PLY shift/reduce conflicts in grammar | Use operator precedence declarations (`precedence` tuple in PLY), debug with `parser.out` |
| Multi-label ML with small dataset | Use `MultiOutputClassifier` + `RandomForest`; generate 500–1000 synthetic programs for adequate coverage |
| AST-to-JSON serialization for frontend | Implement a `.to_dict()` method on every AST node class; serialize recursively |
| Identifying loop-invariant expressions in TAC | Use basic block analysis: track variable definitions inside loop body, check if any operands are modified within the loop |
| Avoiding data leakage in ML training | Feature extraction uses only structural properties (no "did this optimization work?" information leaks into training features) |
| CORS between Flask and browser | Use `flask-cors` with `CORS(app)` |
| Frontend rendering large ASTs | Use a collapsible tree component; limit depth rendered by default |
| Viva demonstration | Keep 5 pre-loaded example programs covering all optimization types |

---

## 10. Development Roadmap

### Phase 0 — Setup (Day 1)
- [ ] Create folder structure
- [ ] Set up Python virtual environment
- [ ] Install: `ply`, `flask`, `flask-cors`, `scikit-learn`, `pandas`, `numpy`, `joblib`
- [ ] Write `config.py`, `app.py` skeleton
- [ ] Write `requirements.txt`

### Phase 1 — Language & Lexer (Day 2)
- [ ] Define formal BNF grammar (`docs/grammar.md`)
- [ ] Implement `lexer.py` with all tokens
- [ ] Write `tests/test_lexer.py` (unit test all token types)

### Phase 2 — Parser & AST (Day 3)
- [ ] Implement `parser.py` (grammar rules + precedence)
- [ ] Implement `ast_nodes.py` (node class hierarchy)
- [ ] Implement `ast_builder.py`
- [ ] Write `tests/test_parser.py`

### Phase 3 — Semantic Analysis (Day 4)
- [ ] Implement `symbol_table.py` (scoped)
- [ ] Implement `semantic_analyzer.py` (type check, undeclared vars)
- [ ] Write `tests/test_semantic.py`

### Phase 4 — IR Generation (Day 5)
- [ ] Implement `ir_generator.py` (TAC emission)
- [ ] Write `tests/test_ir.py`

### Phase 5 — Optimization Passes (Day 6)
- [ ] Implement all 8 optimization passes in `optimizer.py`
- [ ] Write `tests/test_optimizer.py`

### Phase 6 — ML Pipeline (Day 7–8)
- [ ] Implement `feature_extractor.py`
- [ ] Implement `generate_dataset.py` and run it
- [ ] Implement `trainer.py` and train the model
- [ ] Implement `model.py` and `recommendation.py`
- [ ] Write `tests/test_ml.py`

### Phase 7 — Flask API (Day 9)
- [ ] Wire all modules into Flask blueprints
- [ ] Implement `/api/analyze` and `/api/optimize`
- [ ] Test API with Postman / curl

### Phase 8 — Frontend Dashboard (Day 10–11)
- [ ] Build `index.html` layout + tab structure
- [ ] Implement code editor panel
- [ ] Implement phase output panels (tokens, AST, TAC, etc.)
- [ ] Implement Chart.js visualizations
- [ ] Implement AST tree visualizer

### Phase 9 — Integration & Polish (Day 12)
- [ ] End-to-end integration test with 5 example programs
- [ ] Error handling (syntax errors, semantic errors shown in UI)
- [ ] Add pre-loaded demo programs

### Phase 10 — Documentation & Viva Prep (Day 13)
- [ ] Complete `README.md`
- [ ] Write `docs/api_reference.md`
- [ ] Prepare viva Q&A notes

---

## 11. Evaluation Strategy

### Compiler Correctness
- Unit tests for each phase independently
- Golden output comparison: known input → expected tokens / AST / TAC
- At least 10 test programs per phase

### Optimization Correctness
- Semantic equivalence check: ensure TAC before and after produces the same result when simulated
- Count-based metrics: `instructions_before`, `instructions_after`, `reduction_%`

### ML Model Quality
- **Hamming Loss** (fraction of incorrectly predicted labels)
- **F1-Score** per optimization label
- **Precision / Recall** per label
- **Confusion matrix** for each label
- Report shown in dashboard "ML Metrics" tab

### System Evaluation
- 5 benchmark programs demonstrating each optimization type
- Before/after instruction count shown in Chart.js bar chart
- ML confidence scores shown as a radar chart

---

## 12. API Response Schema

```json
{
  "success": true,
  "phases": {
    "tokens": [{"type": "INT", "value": "int", "line": 1}, ...],
    "ast": { "type": "Program", "children": [...] },
    "symbol_table": [{"name": "x", "type": "int", "scope": "main"}],
    "semantic_errors": [],
    "tac_before": ["t1 = 2 + 3", "x = t1", ...],
    "tac_after":  ["x = 5", ...]
  },
  "ml": {
    "features": {"num_loops": 2, "const_fold_opportunities": 3, ...},
    "recommendations": [
      {
        "optimization": "CONSTANT_FOLDING",
        "confidence": 0.94,
        "explanation": "2 constant-foldable expressions detected...",
        "example": "t1 = 2 + 3  →  t1 = 5"
      }
    ]
  },
  "stats": {
    "instructions_before": 18,
    "instructions_after": 11,
    "reduction_percent": 38.9
  }
}
```

---

## 13. Key Design Decisions

| Decision | Rationale |
|---|---|
| **PLY over ANTLR** | PLY is Python-native, well-documented for undergraduate use, no Java dependency |
| **TAC over bytecode** | TAC is the standard IR taught in PCD courses; easy to display and explain |
| **RandomForest over deep learning** | Interpretable, works on small datasets, feature importance is a natural teaching tool |
| **Multi-label classification** | Multiple optimizations can apply simultaneously to the same code |
| **Synthetic dataset** | Allows full control over coverage of all optimization patterns; deterministic labels |
| **Flask blueprints** | Keeps API routes modular; each phase can be tested via its own endpoint |
| **Compiler independent of frontend** | Compiler package has zero Flask/HTML dependencies; can be unit tested in isolation |

---

> **Next Step**: Review and approve this plan. Once approved, implementation begins with **Phase 0 (Setup)** and proceeds phase by phase.

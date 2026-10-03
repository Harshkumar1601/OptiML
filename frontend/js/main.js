/**
 * main.js — Application entrypoint, event wiring, and workflow orchestrator.
 */

document.addEventListener('DOMContentLoaded', () => {
  // Initialize components
  const editor = new CodeEditor('code-input', 'line-numbers', 'demo-presets');
  const charts = new AppCharts();

  // Element References
  const btnAnalyze = document.getElementById('btn-analyze');
  const btnTokenizeOnly = document.getElementById('btn-tokenize-only');
  const btnClear = document.getElementById('btn-clear');
  const backendStatusEl = document.getElementById('backend-status');
  const tabButtons = document.querySelectorAll('.tab-btn');
  const tabPanes = document.querySelectorAll('.tab-pane');
  const errorBanner = document.getElementById('error-diagnostics');
  const errorTitle = document.getElementById('error-title');
  const errorMessage = document.getElementById('error-message');
  const errorList = document.getElementById('error-list');
  const emptyState = document.getElementById('empty-state');
  const overviewContent = document.getElementById('overview-content');

  // Check backend health on load
  checkBackendHealth();

  // Periodically re-check health every 15 seconds
  setInterval(checkBackendHealth, 15000);

  // Tab switching logic
  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetTab = btn.getAttribute('data-tab');
      
      tabButtons.forEach(b => b.classList.remove('active'));
      tabPanes.forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      const pane = document.getElementById(targetTab);
      if (pane) pane.classList.add('active');
    });
  });

  // Action: Clear Editor
  btnClear.addEventListener('click', () => {
    editor.clear();
    hideErrorBanner();
  });

  // Action: Tokenize Only
  btnTokenizeOnly.addEventListener('click', async () => {
    const code = editor.getCode().trim();
    if (!code) return;

    btnTokenizeOnly.disabled = true;
    btnTokenizeOnly.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Tokenizing...';
    hideErrorBanner();

    try {
      const res = await ApiClient.tokenizeSource(code);
      if (res.tokens) {
        PhaseRenderer.renderTokens(
          res.tokens,
          document.getElementById('tokens-table-body'),
          document.getElementById('token-count-badge')
        );
        // Switch to Tokens tab
        document.querySelector('[data-tab="tab-tokens"]').click();
      }
    } catch (err) {
      showError('Tokenization Error', 'Failed to communicate with API.', [err.message]);
    } finally {
      btnTokenizeOnly.disabled = false;
      btnTokenizeOnly.innerHTML = '<i class="fa-solid fa-list-check"></i> Tokenize Only';
    }
  });

  // Action: Run Full Pipeline
  btnAnalyze.addEventListener('click', async () => {
    const code = editor.getCode().trim();
    if (!code) {
      showError('Empty Source Code', 'Please write or select a C-like program to analyze.', []);
      return;
    }

    btnAnalyze.disabled = true;
    btnAnalyze.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Running ML Pipeline...';
    hideErrorBanner();

    try {
      const data = await ApiClient.analyzeSource(code);
      
      if (!data.success) {
        // Show compiler / syntax / semantic error diagnostics
        showError(
          data.error || 'Compiler Error',
          'The code contains syntax or semantic errors preventing full optimization.',
          data.errors || []
        );
        
        // Still render partial phases (tokens, ast if available)
        if (data.phases) {
          if (data.phases.tokens) {
            PhaseRenderer.renderTokens(
              data.phases.tokens,
              document.getElementById('tokens-table-body'),
              document.getElementById('token-count-badge')
            );
          }
        }
        return;
      }

      // Success — render full response across all panels
      renderPipelineResponse(data, charts);

    } catch (err) {
      console.error(err);
      showError(
        'Backend Connection Error',
        'Could not reach Flask backend server. Make sure `python app.py` is running on port 5000.',
        [err.message]
      );
    } finally {
      btnAnalyze.disabled = false;
      btnAnalyze.innerHTML = '<i class="fa-solid fa-play"></i> Run Optimization Pipeline';
    }
  });

  // Helper: Backend Health Check
  async function checkBackendHealth() {
    const health = await ApiClient.getHealth();
    const dot = backendStatusEl.querySelector('.status-dot');
    const label = backendStatusEl.querySelector('.status-label');

    if (health.status === 'ok') {
      dot.className = 'status-dot online';
      label.textContent = 'Backend Online (Port 5000)';
    } else {
      dot.className = 'status-dot offline';
      label.textContent = 'Backend Offline';
    }

    // Load model info if online
    if (health.status === 'ok') {
      const modelInfo = await ApiClient.getModelInfo();
      if (modelInfo) {
        document.getElementById('ml-info-arch').textContent = modelInfo.model_type || 'MultiOutputClassifier';
        document.getElementById('ml-info-samples').textContent = modelInfo.training_samples || 480;
        if (modelInfo.metrics && modelInfo.metrics.hamming_loss !== undefined) {
          document.getElementById('ml-info-hamming').textContent = modelInfo.metrics.hamming_loss;
        }
      }
    }
  }

  // Helper: Render pipeline output across dashboard
  function renderPipelineResponse(data, charts) {
    emptyState.classList.add('hidden');
    overviewContent.classList.remove('hidden');

    const phases = data.phases || {};
    const ml = data.ml || {};
    const stats = data.stats || {};

    // 1. Overview Metrics Cards
    document.getElementById('stat-tac-before').textContent = stats.instructions_before || 0;
    document.getElementById('stat-tac-after').textContent = stats.instructions_after || 0;
    
    const countRed = stats.reduction_count || 0;
    const pctRed = stats.reduction_percent || 0;
    document.getElementById('stat-reduction').textContent = `${countRed} (${pctRed}%)`;

    const appliedPasses = stats.passes_applied || [];
    document.getElementById('stat-passes-count').textContent = `${appliedPasses.length} / 5`;

    // 2. Visual Charts
    charts.updateTACComparison(stats.instructions_before || 0, stats.instructions_after || 0);
    if (ml.recommendations) {
      charts.updateMLConfidence(ml.recommendations);
    }

    // 3. Pass Recommendation Summary Table
    if (ml.recommendations) {
      PhaseRenderer.renderPassSummary(ml.recommendations, document.getElementById('summary-passes-table'));
    }

    // 4. ML Tab Features & Explanations
    if (ml.features) {
      PhaseRenderer.renderFeatures(ml.features, document.getElementById('features-container'));
    }
    if (data.ml && data.ml.recommendations) {
      PhaseRenderer.renderExplanations(data.ml.recommendations, document.getElementById('explanations-container'));
    }

    // 5. TAC Tab
    Visualizer.renderTAC(phases.tac_before, document.getElementById('tac-before-code'), false);
    Visualizer.renderTAC(phases.tac_after, document.getElementById('tac-after-code'), true);

    document.getElementById('count-tac-before').textContent = `${stats.instructions_before || 0} Instructions`;
    document.getElementById('count-tac-after').textContent = `${stats.instructions_after || 0} Instructions`;

    // 6. AST & Symbol Table Tab
    if (phases.ast) {
      Visualizer.renderAST(phases.ast, document.getElementById('ast-tree-container'));
    }
    if (phases.symbol_table) {
      PhaseRenderer.renderSymbolTable(
        phases.symbol_table,
        document.getElementById('symbol-table-body'),
        document.getElementById('symbol-count-badge')
      );
    }

    // 7. Tokens Tab
    if (phases.tokens) {
      PhaseRenderer.renderTokens(
        phases.tokens,
        document.getElementById('tokens-table-body'),
        document.getElementById('token-count-badge')
      );
    }
  }

  function showError(title, msg, list = []) {
    errorTitle.textContent = title;
    errorMessage.textContent = msg;
    errorList.innerHTML = list.map(e => `<li>${typeof e === 'object' ? JSON.stringify(e) : e}</li>`).join('');
    errorBanner.classList.remove('hidden');
  }

  function hideErrorBanner() {
    errorBanner.classList.add('hidden');
  }
});

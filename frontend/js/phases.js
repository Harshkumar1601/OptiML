/**
 * phases.js — Renderers for individual compiler phase views and result displays.
 */

class PhaseRenderer {

  /**
   * Render tokens table in Tab 5.
   */
  static renderTokens(tokens, tableBodyEl, badgeEl) {
    if (badgeEl) badgeEl.textContent = `${tokens ? tokens.length : 0} Tokens`;
    
    if (!tokens || tokens.length === 0) {
      tableBodyEl.innerHTML = '<tr><td colspan="4" class="text-center">No tokens found.</td></tr>';
      return;
    }

    const rows = tokens.map((tok, idx) => `
      <tr>
        <td>#${idx + 1}</td>
        <td><span class="badge badge-outline">${tok.type}</span></td>
        <td><code>${this._escapeHtml(String(tok.value))}</code></td>
        <td>Line ${tok.line}</td>
      </tr>
    `);
    tableBodyEl.innerHTML = rows.join('');
  }

  /**
   * Render Symbol Table in Tab 4.
   */
  static renderSymbolTable(symbols, tableBodyEl, badgeEl) {
    if (badgeEl) badgeEl.textContent = `${symbols ? symbols.length : 0} Symbols`;

    if (!symbols || symbols.length === 0) {
      tableBodyEl.innerHTML = '<tr><td colspan="6" class="text-center">No symbols declared.</td></tr>';
      return;
    }

    const rows = symbols.map(sym => `
      <tr>
        <td><strong><code>${sym.name}</code></strong></td>
        <td><span class="badge ${sym.category === 'function' ? 'badge-info' : 'badge-outline'}">${sym.category || 'variable'}</span></td>
        <td><code>${sym.type}</code></td>
        <td>Level ${sym.scope_level}</td>
        <td>${sym.enclosing_function || 'global'}</td>
        <td>Line ${sym.line}</td>
      </tr>
    `);
    tableBodyEl.innerHTML = rows.join('');
  }

  /**
   * Render 15 structural ML features in Tab 2.
   */
  static renderFeatures(features, containerEl) {
    containerEl.innerHTML = '';
    if (!features) {
      containerEl.innerHTML = '<p class="placeholder-text">No features extracted.</p>';
      return;
    }

    const featureKeys = [
      'num_loops', 'loop_depth_max', 'num_functions', 'num_assignments',
      'num_branches', 'tac_total_instructions', 'temp_var_count', 'const_literal_count',
      'add_op_count', 'mul_op_count', 'div_op_count', 'num_unique_vars',
      'repeated_rhs_count', 'mul_by_power_of_2', 'single_use_temp_count'
    ];

    featureKeys.forEach((key, idx) => {
      const val = features[key] !== undefined ? features[key] : 0;
      const box = document.createElement('div');
      box.className = 'feature-box';
      box.innerHTML = `
        <span class="feature-name">F${idx + 1}: ${key}</span>
        <span class="feature-val">${val}</span>
      `;
      containerEl.appendChild(box);
    });
  }

  /**
   * Render pass explanations in Tab 2.
   */
  static renderExplanations(explanations, containerEl) {
    containerEl.innerHTML = '';
    if (!explanations || explanations.length === 0) {
      containerEl.innerHTML = '<p class="placeholder-text">No explanations available.</p>';
      return;
    }

    explanations.forEach(exp => {
      const card = document.createElement('div');
      const isApplied = exp.applied;
      card.className = `explanation-card ${isApplied ? 'recommended' : 'skipped'}`;
      card.innerHTML = `
        <div class="exp-header">
          <span class="exp-title">${exp.pass.replace('_', ' ')}</span>
          <span class="badge ${isApplied ? 'badge-success' : 'badge-outline'}">${isApplied ? 'APPLIED' : 'SKIPPED'}</span>
        </div>
        <div class="exp-text">${exp.explanation}</div>
      `;
      containerEl.appendChild(card);
    });
  }

  /**
   * Render summary table of ML pass recommendations in Tab 1 Overview.
   */
  static renderPassSummary(recommendations, tableBodyEl) {
    if (!recommendations || recommendations.length === 0) {
      tableBodyEl.innerHTML = '<tr><td colspan="5" class="text-center">No pass recommendations.</td></tr>';
      return;
    }

    const rows = recommendations.map(rec => {
      const confPct = Math.round(rec.confidence * 100);
      const isApplied = rec.applied;
      return `
        <tr>
          <td><strong>${rec.pass.replace('_', ' ')}</strong></td>
          <td>
            <div style="display: flex; align-items: center; gap: 0.5rem;">
              <span style="font-family: var(--font-code); font-weight: 600;">${rec.confidence.toFixed(2)} (${confPct}%)</span>
            </div>
          </td>
          <td>
            <span class="badge ${isApplied ? 'badge-success' : 'badge-danger'}">${isApplied ? 'RECOMMENDED' : 'SKIPPED'}</span>
          </td>
          <td>
            <span class="badge ${isApplied ? 'badge-measured' : 'badge-outline'}">${isApplied ? 'APPLIED TO TAC' : 'NOT APPLIED'}</span>
          </td>
          <td>
            <span class="badge badge-estimated">${rec.result_type || 'ESTIMATED'}</span>
          </td>
        </tr>
      `;
    });
    tableBodyEl.innerHTML = rows.join('');
  }

  static _escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }
}

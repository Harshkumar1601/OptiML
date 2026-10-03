/**
 * visualizer.js — Renders interactive AST tree views and TAC diff highlighting.
 */

class Visualizer {
  /**
   * Render AST Node tree into container element.
   * @param {Object} astNode 
   * @param {HTMLElement} container 
   */
  static renderAST(astNode, container) {
    container.innerHTML = '';
    if (!astNode) {
      container.innerHTML = '<p class="placeholder-text">No AST available.</p>';
      return;
    }

    const treeRoot = this._createASTNodeElement(astNode);
    container.appendChild(treeRoot);
  }

  /**
   * Create single AST Node DOM element with children recursively.
   */
  static _createASTNodeElement(node) {
    const nodeDiv = document.createElement('div');
    nodeDiv.className = 'ast-node';

    const header = document.createElement('div');
    header.className = 'ast-node-header';

    const nodeType = document.createElement('span');
    nodeType.className = 'ast-node-type';
    nodeType.textContent = node.type || node.node_type || 'ASTNode';
    header.appendChild(nodeType);

    // Display key node attributes
    const extraDetails = [];
    if (node.name) extraDetails.push(`name: "${node.name}"`);
    if (node.value !== undefined) extraDetails.push(`val: ${node.value}`);
    if (node.op) extraDetails.push(`op: '${node.op}'`);
    if (node.var_type) extraDetails.push(`type: ${node.var_type}`);
    if (node.return_type) extraDetails.push(`ret: ${node.return_type}`);

    if (extraDetails.length > 0) {
      const valSpan = document.createElement('span');
      valSpan.className = 'ast-node-val';
      valSpan.textContent = ` (${extraDetails.join(', ')})`;
      header.appendChild(valSpan);
    }

    if (node.line) {
      const lineSpan = document.createElement('span');
      lineSpan.className = 'ast-node-line';
      lineSpan.textContent = ` [L${node.line}]`;
      header.appendChild(lineSpan);
    }

    nodeDiv.appendChild(header);

    // Collect child AST nodes or arrays of children
    const childKeys = ['statements', 'declarations', 'functions', 'body', 'init', 'condition', 'update', 'left', 'right', 'operand', 'expr', 'value', 'args', 'params', 'then_branch', 'else_branch'];
    const childrenContainer = document.createElement('div');
    childrenContainer.className = 'ast-children';
    let hasChildren = false;

    for (const key of Object.keys(node)) {
      if (key === 'type' || key === 'line' || key === 'name' || key === 'value' || key === 'op' || key === 'var_type' || key === 'return_type') continue;

      const child = node[key];
      if (Array.isArray(child) && child.length > 0) {
        child.forEach(c => {
          if (c && typeof c === 'object' && (c.type || c.node_type)) {
            childrenContainer.appendChild(this._createASTNodeElement(c));
            hasChildren = true;
          }
        });
      } else if (child && typeof child === 'object' && (child.type || child.node_type)) {
        childrenContainer.appendChild(this._createASTNodeElement(child));
        hasChildren = true;
      }
    }

    if (hasChildren) {
      nodeDiv.appendChild(childrenContainer);
      
      // Click to toggle expand/collapse
      header.addEventListener('click', (e) => {
        e.stopPropagation();
        const isHidden = childrenContainer.style.display === 'none';
        childrenContainer.style.display = isHidden ? 'block' : 'none';
        header.style.opacity = isHidden ? '1' : '0.6';
      });
    }

    return nodeDiv;
  }

  /**
   * Render TAC code with line numbers & diff styling.
   * @param {Array|string} tacInstructions 
   * @param {HTMLElement} element 
   * @param {Array} removedLines 
   */
  static renderTAC(tacInstructions, element, isAfter = false) {
    if (!tacInstructions || tacInstructions.length === 0) {
      element.innerHTML = '<code>// No TAC instructions generated</code>';
      return;
    }

    let lines = [];
    if (typeof tacInstructions === 'string') {
      lines = tacInstructions.split('\n');
    } else if (Array.isArray(tacInstructions)) {
      lines = tacInstructions.map(instr => {
        if (typeof instr === 'string') return instr;
        // Format TACInstruction dict object
        const op = instr.op || '';
        const dst = instr.result ? `${instr.result} = ` : '';
        const arg1 = instr.arg1 || '';
        const arg2 = instr.arg2 ? ` ${instr.arg2}` : '';
        
        if (op === 'LABEL') return `${arg1}:`;
        if (op === 'JUMP') return `goto ${arg1}`;
        if (op === 'JUMP_IF_FALSE') return `ifFalse ${arg1} goto ${arg2}`;
        if (op === 'RETURN') return `return ${arg1}`;
        if (op === 'PARAM') return `param ${arg1}`;
        if (op === 'CALL') return `${dst}call ${arg1}, ${arg2}`;
        if (op === '=') return `${dst}${arg1}`;
        
        return `${dst}${arg1} ${op}${arg2}`.trim();
      });
    }

    const htmlLines = lines.map((line, idx) => {
      const lineNum = String(idx + 1).padStart(2, ' ');
      let cssClass = '';
      if (isAfter && line.includes('<<')) {
        cssClass = 'diff-added';
      }
      return `<span class="${cssClass}">${lineNum} | ${this._escapeHtml(line)}</span>`;
    });

    element.innerHTML = htmlLines.join('\n');
  }

  static _escapeHtml(str) {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }
}

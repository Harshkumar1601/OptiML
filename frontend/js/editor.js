/**
 * editor.js — Manages source code editor, presets, and line numbering.
 */

const PRESET_PROGRAMS = {
  constant_folding: `// Demo 1: Constant Folding Optimization
int main() {
    int a = 10 + 20 * 2;
    float b = 3.5 + 4.5;
    return a;
}`,

  constant_propagation: `// Demo 2: Constant Propagation
int main() {
    int x = 5;
    int y = 10;
    int z = x + y + 2;
    return z;
}`,

  cse: `// Demo 3: Common Subexpression Elimination (CSE)
int main() {
    int a = 4;
    int b = 8;
    int x = a * b + 10;
    int y = a * b + 10;
    int z = x + y;
    return z;
}`,

  dead_code: `// Demo 4: Dead Code Elimination (DCE)
int main() {
    int x = 10;
    int unused_var = x + 5;
    int dead_copy = 100;
    int target = 42;
    return target;
}`,

  strength_reduction: `// Demo 5: Strength Reduction (SR)
int main() {
    int x = 15;
    int y = x * 4;
    int z = x * 8;
    return y + z;
}`,

  multi_pass: `// Demo 6: Comprehensive Multi-Pass Optimization
int main() {
    int a = 10 + 5;           // Constant Folding
    int b = a * 2;            // Constant Propagation
    int x = a * 4;            // Strength Reduction (x * 4 -> x << 2)
    int y = a * 4;            // Common Subexpression Elimination (reuse x)
    int unused = 999;         // Dead Code Elimination
    return b + x + y;
}`
};

class CodeEditor {
  constructor(textareaId, lineNumbersId, presetSelectId) {
    this.textarea = document.getElementById(textareaId);
    this.lineNumbers = document.getElementById(lineNumbersId);
    this.presetSelect = document.getElementById(presetSelectId);

    this.init();
  }

  init() {
    // Sync line numbers on input & scroll
    this.textarea.addEventListener('input', () => this.updateLineNumbers());
    this.textarea.addEventListener('scroll', () => {
      this.lineNumbers.scrollTop = this.textarea.scrollTop;
    });

    // Preset selector listener
    if (this.presetSelect) {
      this.presetSelect.addEventListener('change', (e) => {
        const key = e.target.value;
        if (PRESET_PROGRAMS[key]) {
          this.setCode(PRESET_PROGRAMS[key]);
        }
      });
    }

    // Tab key support in textarea
    this.textarea.addEventListener('keydown', (e) => {
      if (e.key === 'Tab') {
        e.preventDefault();
        const start = this.textarea.selectionStart;
        const end = this.textarea.selectionEnd;
        this.textarea.value = this.textarea.value.substring(0, start) + '    ' + this.textarea.value.substring(end);
        this.textarea.selectionStart = this.textarea.selectionEnd = start + 4;
        this.updateLineNumbers();
      }
    });

    // Load initial multi-pass code
    this.setCode(PRESET_PROGRAMS.multi_pass);
  }

  getCode() {
    return this.textarea.value;
  }

  setCode(code) {
    this.textarea.value = code;
    this.updateLineNumbers();
  }

  clear() {
    this.textarea.value = '';
    this.updateLineNumbers();
  }

  updateLineNumbers() {
    const lines = this.textarea.value.split('\n').length;
    let numsHtml = '';
    for (let i = 1; i <= lines; i++) {
      numsHtml += `${i}<br>`;
    }
    this.lineNumbers.innerHTML = numsHtml;
  }
}

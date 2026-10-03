/**
 * api.js — API client wrapper for Flask backend communications.
 */
const API_BASE_URL = 'http://127.0.0.1:5000/api';

class ApiClient {
  /**
   * Check backend health status.
   */
  static async getHealth() {
    try {
      const response = await fetch(`${API_BASE_URL}/health`);
      if (!response.ok) throw new Error(`HTTP Error ${response.status}`);
      return await response.json();
    } catch (err) {
      console.warn('Backend health check failed:', err);
      return { status: 'offline', model_loaded: false };
    }
  }

  /**
   * Fetch ML model metrics & info.
   */
  static async getModelInfo() {
    try {
      const response = await fetch(`${API_BASE_URL}/model`);
      if (!response.ok) throw new Error(`HTTP Error ${response.status}`);
      return await response.json();
    } catch (err) {
      console.error('Failed to fetch model metrics:', err);
      return null;
    }
  }

  /**
   * Run full 10-step compiler + ML pipeline.
   * @param {string} sourceCode 
   */
  static async analyzeSource(sourceCode) {
    const response = await fetch(`${API_BASE_URL}/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ source_code: sourceCode }),
    });
    return await response.json();
  }

  /**
   * Tokenize source code only (fast-path).
   * @param {string} sourceCode 
   */
  static async tokenizeSource(sourceCode) {
    const response = await fetch(`${API_BASE_URL}/tokenize`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ source_code: sourceCode }),
    });
    return await response.json();
  }
}

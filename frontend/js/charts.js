/**
 * charts.js — Chart.js visualizer for ML confidence scores & instruction count stats.
 */

class AppCharts {
  constructor() {
    this.tacChart = null;
    this.mlChart = null;
  }

  /**
   * Render or update TAC instruction reduction comparison bar chart.
   */
  updateTACComparison(beforeCount, afterCount) {
    const ctx = document.getElementById('chart-tac-comparison');
    if (!ctx) return;

    if (this.tacChart) {
      this.tacChart.destroy();
    }

    this.tacChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: ['Before Optimization', 'After Optimization'],
        datasets: [{
          label: 'TAC Instruction Count',
          data: [beforeCount, afterCount],
          backgroundColor: [
            'rgba(239, 68, 68, 0.7)',   // Red
            'rgba(16, 185, 129, 0.8)'   // Green
          ],
          borderColor: [
            '#ef4444',
            '#10b981'
          ],
          borderWidth: 1.5,
          borderRadius: 8
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (context) => ` ${context.raw} Instructions (MEASURED)`
            }
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: { color: '#9ca3af', precision: 0 },
            grid: { color: 'rgba(255, 255, 255, 0.06)' }
          },
          x: {
            ticks: { color: '#f3f4f6', font: { weight: '600' } },
            grid: { display: false }
          }
        }
      }
    });
  }

  /**
   * Render or update ML model pass recommendation confidence horizontal bar chart.
   */
  updateMLConfidence(recommendations) {
    const ctx = document.getElementById('chart-ml-confidence');
    if (!ctx) return;

    if (this.mlChart) {
      this.mlChart.destroy();
    }

    if (!recommendations || recommendations.length === 0) return;

    const labels = recommendations.map(r => r.pass.replace('_', ' '));
    const scores = recommendations.map(r => Math.round(r.confidence * 100));
    const bgColors = recommendations.map(r => r.applied ? 'rgba(16, 185, 129, 0.8)' : 'rgba(107, 114, 128, 0.5)');
    const borderColors = recommendations.map(r => r.applied ? '#10b981' : '#6b7280');

    this.mlChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'ML Model Confidence (%)',
          data: scores,
          backgroundColor: bgColors,
          borderColor: borderColors,
          borderWidth: 1.5,
          borderRadius: 6
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (context) => {
                const rec = recommendations[context.dataIndex];
                const status = rec.applied ? 'RECOMMENDED & APPLIED' : 'SKIPPED (Below 50%)';
                return ` ${rec.confidence.toFixed(2)} (${scores[context.dataIndex]}%) — ${status}`;
              }
            }
          }
        },
        scales: {
          x: {
            min: 0,
            max: 100,
            ticks: {
              color: '#9ca3af',
              callback: (value) => `${value}%`
            },
            grid: { color: 'rgba(255, 255, 255, 0.06)' }
          },
          y: {
            ticks: { color: '#f3f4f6', font: { size: 11, weight: '500' } },
            grid: { display: false }
          }
        }
      }
    });
  }
}

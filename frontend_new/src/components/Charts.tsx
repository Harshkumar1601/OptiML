import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

const CHART_DEFAULTS = {
  color: '#8892a4',
  font: { family: 'Inter, sans-serif', size: 11 },
};

// Dark chart defaults
ChartJS.defaults.color = CHART_DEFAULTS.color;
ChartJS.defaults.font.family = CHART_DEFAULTS.font.family;
ChartJS.defaults.font.size = CHART_DEFAULTS.font.size;

// ─── TAC reduction bar chart ─────────────────────────────────────────────────
export function TacComparisonChart({
  before,
  after,
}: {
  before: number;
  after: number;
}) {
  const data = {
    labels: ['Before Optimization', 'After Optimization'],
    datasets: [
      {
        label: 'Instructions',
        data: [before, after],
        backgroundColor: ['rgba(239,68,68,0.65)', 'rgba(16,185,129,0.75)'],
        borderColor: ['#ef4444', '#10b981'],
        borderWidth: 1,
        borderRadius: 4,
      },
    ],
  };

  const options: any = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx: { raw: unknown }) => ` ${ctx.raw} instructions`,
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        ticks: { precision: 0, color: '#8892a4' },
        grid: { color: '#1e2736' },
      },
      x: {
        ticks: { color: '#e2e8f0', font: { weight: 'normal' } },
        grid: { display: false },
      },
    },
  };

  return <Bar data={data} options={options} />;
}

// ─── ML confidence horizontal bar chart ──────────────────────────────────────
export function ConfidenceChart({
  recommendations,
}: {
  recommendations: Array<{
    pass: string;
    confidence: number;
    applied: boolean;
  }>;
}) {
  const labels = recommendations.map((r) => {
    const abbr: Record<string, string> = {
      CONSTANT_FOLDING: 'CF',
      CONSTANT_PROPAGATION: 'CP',
      CSE: 'CSE',
      DEAD_CODE_ELIMINATION: 'DCE',
      STRENGTH_REDUCTION: 'SR',
    };
    return abbr[r.pass] ?? r.pass.slice(0, 4);
  });

  const data = {
    labels,
    datasets: [
      {
        label: 'Confidence',
        data: recommendations.map((r) => Math.round(r.confidence * 100)),
        backgroundColor: recommendations.map((r) =>
          r.applied ? 'rgba(16,185,129,0.75)' : 'rgba(55,65,81,0.6)'
        ),
        borderColor: recommendations.map((r) =>
          r.applied ? '#10b981' : '#374151'
        ),
        borderWidth: 1,
        borderRadius: 3,
      },
    ],
  };

  const options: any = {
    indexAxis: 'y' as const,
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx: { raw: unknown; dataIndex: number }) => {
            const rec = recommendations[ctx.dataIndex];
            return ` ${rec.confidence.toFixed(2)} (${ctx.raw}%) — ${rec.applied ? 'Applied' : 'Skipped'}`;
          },
        },
      },
    },
    scales: {
      x: {
        min: 0,
        max: 100,
        ticks: {
          color: '#8892a4',
          callback: (v: unknown) => `${v}%`,
        },
        grid: { color: '#1e2736' },
      },
      y: {
        ticks: { color: '#e2e8f0', font: { weight: 'normal' } },
        grid: { display: false },
      },
    },
  };

  return <Bar data={data} options={options} />;
}

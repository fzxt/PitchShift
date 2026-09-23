import type { Comparison, Pitcher } from './types';

const PITCHES: Record<string, [string, string]> = {
  FF: ['Four-seam', '#b2a242'],
  SI: ['Sinker', '#cf8756'],
  FC: ['Cutter', '#67969b'],
  SL: ['Slider', '#8d86b7'],
  ST: ['Sweeper', '#b497ca'],
  CU: ['Curveball', '#cf9a83'],
  KC: ['Knuckle curve', '#b79577'],
  CH: ['Changeup', '#76985b'],
  FS: ['Splitter', '#599087'],
  SV: ['Slurve', '#bb7d88'],
  KN: ['Knuckleball', '#8197a5'],
};
export const pitchName = (type: string) => PITCHES[type]?.[0] ?? type;
export const pitchColor = (type: string) => PITCHES[type]?.[1] ?? '#879777';
export const finite = (n: unknown): n is number => typeof n === 'number' && Number.isFinite(n);
export const fmt = (n: number | null | undefined, digits = 1) =>
  finite(n) ? n.toFixed(digits) : '—';
export const count = (n: number) => n.toLocaleString('en-US');
export const signed = (n: number | null | undefined, digits = 1) =>
  finite(n) ? `${n > 0 ? '+' : n < 0 ? '−' : ''}${Math.abs(n).toFixed(digits)}` : '—';
export function date(value: string | null | undefined, year = false) {
  if (!value) return '—';
  const parsed = new Date(`${value.slice(0, 10)}T12:00:00Z`);
  return Number.isNaN(parsed.valueOf())
    ? '—'
    : parsed.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        ...(year ? { year: 'numeric' } : {}),
        timeZone: 'UTC',
      });
}
export const dateRange = (a: string | null, b: string | null) =>
  a === b ? date(a) : `${date(a)} – ${date(b)}`;
export const metricValue = (n: number, metric: Comparison) =>
  `${fmt(n)}${['pp', '%'].includes(metric.unit) ? '%' : metric.unit === 'in' ? '″' : ` ${metric.unit}`}`;
export const strength = (p: Pitcher) =>
  Math.max(0, ...p.alerts.map((a) => Math.abs(a.delta) / a.practicalThreshold));
export function takeaway(p: Pitcher) {
  if (p.status === 'insufficient')
    return 'There are not enough pitches in one or both windows for a reliable comparison. Add more games before interpreting changes.';
  const a = p.alerts[0];
  if (!a)
    return 'No eligible metric clears both the uncertainty and practical-change screens. That does not rule out a change; keep monitoring the next outing.';
  return `${a.pitchName || pitchName(a.pitchType)} ${a.label.toLowerCase()} moved from ${metricValue(a.baseline, a)} to ${metricValue(a.recent, a)}. ${a.interpretation || 'Review recent video and the game-by-game trend to see whether the change persists.'}`;
}
export function exportScoutingCard(p: Pitcher, generatedAt: string, window: string) {
  const lines = [
    `# ${p.name} — PitchShift scouting card`,
    '',
    `Team: ${p.team || 'MLB'} | Throws: ${p.throws || 'Unknown'}`,
    `Recent: ${p.recentStart} to ${p.recentEnd} (${p.recentCount} pitches)`,
    `Baseline: ${p.baselineStart} to ${p.baselineEnd} (${p.baselineCount} pitches)`,
    '',
    '## Scouting takeaway',
    '',
    takeaway(p),
    '',
    '## Change signals',
    '',
  ];
  if (!p.alerts.length) lines.push('No eligible metric clears the screening rules.');
  for (const a of p.alerts)
    lines.push(
      `- ${a.pitchName || pitchName(a.pitchType)} / ${a.label}: ${metricValue(a.baseline, a)} -> ${metricValue(a.recent, a)} (${signed(a.delta)} ${a.unit}); n=${a.baselineN}/${a.recentN}; approximate 95% difference interval ${a.interval?.map((v) => signed(v)).join(' to ') || 'unavailable'} ${a.unit}.`,
    );
  lines.push(
    '',
    '## Limitations',
    '',
    'Exploratory change screens, not calibrated probabilities or causal findings. Pitches are correlated within outings. Multiple comparisons can yield false signals. Opponents, counts, tracking conditions and subsequent outings require review.',
    '',
    'Source: Baseball Savant public Statcast pitch data. All comparisons are within the 2026 season.',
    'Methodology and reproducible code: https://github.com/fzxt/PitchShift',
    '',
    `Generated from snapshot: ${generatedAt}`,
  );
  const url = URL.createObjectURL(
    new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' }),
  );
  const link = document.createElement('a');
  link.href = url;
  link.download = `pitchshift-${p.name.toLowerCase().replace(/[^a-z0-9]+/g, '-')}-${window}.md`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

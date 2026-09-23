import { date, finite, fmt, pitchColor, pitchName } from '../format';
import type { Pitcher } from '../types';

interface ChartProps { pitcher: Pitcher; type: string }
export function PitchDot({ type }: { type: string }) { return <span className="pitch-dot" style={{ background: pitchColor(type) }} />; }

export function ScatterPlot({ pitcher, type, kind }: ChartProps & { kind: 'movement' | 'location' }) {
  const width = 380, height = 292, left = 48, right = 22, top = 18, bottom = 43;
  const movement = kind === 'movement';
  const limits = movement ? [-25, 25, -25, 25] : [-2.6, 2.6, 0, 5.2];
  const xKey = movement ? 'x' : 'px', yKey = movement ? 'z' : 'pz';
  const x = (n: number) => left + (n - limits[0]) / (limits[1] - limits[0]) * (width - left - right);
  const y = (n: number) => height - bottom - (n - limits[2]) / (limits[3] - limits[2]) * (height - top - bottom);
  const ticks = movement ? [-20, -10, 0, 10, 20] : [-2, -1, 0, 1, 2];
  const yTicks = movement ? ticks : [0, 1, 2, 3, 4, 5];
  const points = (['baseline', 'recent'] as const).flatMap(period => pitcher.points[period].filter(p => type === 'all' || p.type === type).map(p => ({ ...p, period })));
  const valid = points.filter(p => finite(p[xKey]) && finite(p[yKey]));
  const visible = valid.filter(p => p[xKey]! >= limits[0] && p[xKey]! <= limits[1] && p[yKey]! >= limits[2] && p[yKey]! <= limits[3]);
  const omitted = valid.length - visible.length;
  return <svg className="plot" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${movement ? 'Pitch movement' : 'Pitch location'} comparison for ${pitcher.name}. Outlined points are baseline; filled points are recent.`}>
    <title>{movement ? 'Movement' : 'Location'} — baseline vs recent</title>
    {ticks.map(n => <g key={`x${n}`}><line className={n === 0 ? 'axis' : 'grid'} x1={x(n)} y1={top} x2={x(n)} y2={height - bottom} /><text x={x(n)} y={height - bottom + 16} textAnchor="middle">{n}</text></g>)}
    {yTicks.map(n => <g key={`y${n}`}><line className={movement && n === 0 ? 'axis' : 'grid'} x1={left} y1={y(n)} x2={width - right} y2={y(n)} /><text x={left - 10} y={y(n) + 3} textAnchor="end">{n}</text></g>)}
    {!movement && <g><rect x={x(-.7083)} y={y(3.5)} width={x(.7083) - x(-.7083)} height={y(1.5) - y(3.5)} fill="#f3f5ed" fillOpacity=".6" stroke="#b4c1a3" strokeWidth="1.3" />{[1, 2].map(i => <g key={i}><line x1={x(-.7083 + 1.4166 * i / 3)} x2={x(-.7083 + 1.4166 * i / 3)} y1={y(3.5)} y2={y(1.5)} stroke="#dce3d2" /><line x1={x(-.7083)} x2={x(.7083)} y1={y(1.5 + 2 * i / 3)} y2={y(1.5 + 2 * i / 3)} stroke="#dce3d2" /></g>)}</g>}
    {visible.map((p, i) => <circle key={i} cx={x(p[xKey]!)} cy={y(p[yKey]!)} r={p.period === 'recent' ? 3.1 : 3} fill={p.period === 'recent' ? pitchColor(p.type) : 'none'} fillOpacity=".75" stroke={pitchColor(p.type)} strokeOpacity={p.period === 'recent' ? '.9' : '.35'} strokeWidth="1"><title>{pitchName(p.type)} · {p.period}: {fmt(p[xKey])}, {fmt(p[yKey])} {movement ? 'in' : 'ft'}</title></circle>)}
    <text className="axis-label" x={(width + left - right) / 2} y={height - 6} textAnchor="middle">{movement ? 'Horizontal break (in)' : 'Horizontal location (ft)'}</text>
    <text className="axis-label" transform={`translate(13 ${(height - bottom + top) / 2}) rotate(-90)`} textAnchor="middle">{movement ? 'Induced vertical break (in)' : 'Height (ft)'}</text>
    {!visible.length && <text x={width / 2} y={height / 2} textAnchor="middle">No tracked pitches in this view</text>}
    {omitted > 0 && <text x={width - right} y="12" textAnchor="end">{omitted} outside chart range</text>}
  </svg>;
}

export function VelocityTimeline({ pitcher, type }: ChartProps) {
  const data = pitcher.timeline.filter(p => finite(p.velocity) && (type === 'all' || p.pitchType === type));
  const width = 760, height = 205, left = 48, right = 25, top = 22, bottom = 38;
  if (!data.length) return <p className="empty-state">Not enough velocity data for this pitch.</p>;
  const dates = [...new Set(data.map(p => p.date))].sort();
  const start = Date.parse(dates[0]), end = Date.parse(dates.at(-1)!);
  const min = Math.floor(Math.min(...data.map(p => p.velocity)) - 1), max = Math.ceil(Math.max(...data.map(p => p.velocity)) + 1);
  const x = (d: string) => left + (end === start ? .5 : (Date.parse(d) - start) / (end - start)) * (width - left - right);
  const y = (n: number) => height - bottom - (n - min) / Math.max(1, max - min) * (height - bottom - top);
  const recentX = Math.min(width - right, Math.max(left, x(pitcher.recentStart)));
  const labels = [...new Set([dates[0], dates[Math.floor((dates.length - 1) / 2)], dates.at(-1)!])];
  return <svg className="plot" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Mean pitch velocity by outing for ${pitcher.name}`}>
    <title>Velocity by outing, colored by pitch type</title>
    {[0, 1, 2, 3, 4].map(i => { const n = min + (max - min) * i / 4; return <g key={i}><line className="grid" x1={left} x2={width - right} y1={y(n)} y2={y(n)} /><text x={left - 10} y={y(n) + 3} textAnchor="end">{fmt(n, 0)}</text></g>; })}
    <rect x={recentX} y={top} width={Math.max(0, width - right - recentX)} height={height - top - bottom} fill="#eaf0df" fillOpacity=".55" />
    <text x={width - right} y="12" textAnchor="end">Recent window shaded · outing means may cross boundary</text>
    {[...new Set(data.map(p => p.pitchType))].map(pitchType => { const series = data.filter(p => p.pitchType === pitchType).sort((a, b) => a.date.localeCompare(b.date)); return <g key={pitchType}><polyline points={series.map(p => `${x(p.date)},${y(p.velocity)}`).join(' ')} fill="none" stroke={pitchColor(pitchType)} strokeWidth="1.5" strokeOpacity=".75" />{series.map(p => <circle key={p.date} cx={x(p.date)} cy={y(p.velocity)} r="3" fill={pitchColor(pitchType)}><title>{pitchName(pitchType)} · {date(p.date)}: {fmt(p.velocity)} mph ({p.count} pitches)</title></circle>)}</g>; })}
    {labels.map(d => <text key={d} x={x(d)} y={height - 15} textAnchor="middle">{date(d)}</text>)}
  </svg>;
}

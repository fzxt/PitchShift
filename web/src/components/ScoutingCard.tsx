import { useState } from 'react';
import type { Comparison, Pitcher, WindowSize } from '../types';
import {
  count,
  dateRange,
  exportScoutingCard,
  finite,
  fmt,
  metricValue,
  pitchColor,
  pitchName,
  signed,
  takeaway,
} from '../format';
import { PitchDot, ScatterPlot, VelocityTimeline } from './Charts';

interface Props {
  pitcher: Pitcher;
  window: WindowSize;
  onWindow: (window: WindowSize) => void;
  saved: boolean;
  onSave: () => void;
  onMethod: () => void;
  generatedAt: string;
  onToast: (message: string) => void;
}
function SignalCard({ signal }: { signal: Comparison }) {
  return (
    <div className="signal-card">
      <div className="signal-type">
        <PitchDot type={signal.pitchType} />
        {signal.pitchName || pitchName(signal.pitchType)}
      </div>
      <h4>{signal.label}</h4>
      <div className="signal-value">
        {signed(signal.delta)}
        <span>{signal.unit}</span>
      </div>
      <div className="signal-comparison">
        {metricValue(signal.baseline, signal)} <span aria-hidden="true">→</span>{' '}
        <b>{metricValue(signal.recent, signal)}</b>
      </div>
      <small className="signal-sample">
        n = {count(signal.baselineN)} → {count(signal.recentN)}
      </small>
    </div>
  );
}
function ArsenalTable({ pitcher }: { pitcher: Pitcher }) {
  return (
    <div className="table-wrap">
      <table>
        <caption className="sr-only">
          Pitch usage and velocity in the baseline and recent windows
        </caption>
        <thead>
          <tr>
            <th scope="col">Pitch</th>
            <th scope="col">Usage</th>
            <th scope="col">Δ usage</th>
            <th scope="col">Velocity</th>
            <th scope="col">Δ velo</th>
            <th scope="col">n recent</th>
          </tr>
        </thead>
        <tbody>
          {pitcher.arsenal.map((a) => (
            <tr key={a.pitchType}>
              <td>
                <PitchDot type={a.pitchType} />
                {a.name || pitchName(a.pitchType)}
              </td>
              <td>
                <span className="usage-bar">
                  <i
                    style={{
                      width: `${Math.max(0, Math.min(100, a.recentUsage ?? 0))}%`,
                      background: pitchColor(a.pitchType),
                    }}
                  />
                </span>
                {fmt(a.baselineUsage, 0)} → {fmt(a.recentUsage, 0)}%
              </td>
              <td
                className={
                  (a.recentUsage ?? 0) >= (a.baselineUsage ?? 0)
                    ? 'delta-positive'
                    : 'delta-negative'
                }
              >
                {signed(
                  finite(a.recentUsage) && finite(a.baselineUsage)
                    ? a.recentUsage - a.baselineUsage
                    : null,
                )}{' '}
                pp
              </td>
              <td>
                {fmt(a.baselineVelocity)} → {fmt(a.recentVelocity)}
              </td>
              <td>
                {finite(a.recentVelocity) && finite(a.baselineVelocity)
                  ? signed(a.recentVelocity - a.baselineVelocity)
                  : '—'}
              </td>
              <td>{count(a.recentCount)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function MetricTable({ pitcher }: { pitcher: Pitcher }) {
  if (!pitcher.metrics.length)
    return <p className="no-metrics">No comparisons meet minimum sample requirements.</p>;
  const screened = new Set(pitcher.alerts.map((a) => `${a.pitchType}:${a.metric}`));
  return (
    <div className="table-wrap">
      <table>
        <caption className="sr-only">
          All eligible comparisons with sample sizes and approximate difference intervals
        </caption>
        <thead>
          <tr>
            <th scope="col">Pitch / metric</th>
            <th scope="col">Baseline</th>
            <th scope="col">Recent</th>
            <th scope="col">Δ</th>
            <th scope="col">95% interval</th>
            <th scope="col">n</th>
            <th scope="col">Screen</th>
          </tr>
        </thead>
        <tbody>
          {pitcher.metrics.map((m) => (
            <tr key={`${m.pitchType}:${m.metric}`}>
              <td>
                <PitchDot type={m.pitchType} />
                {pitchName(m.pitchType)} · {m.label}
              </td>
              <td>{metricValue(m.baseline, m)}</td>
              <td>{metricValue(m.recent, m)}</td>
              <td>
                {signed(m.delta)} {m.unit}
              </td>
              <td>{m.interval ? `${signed(m.interval[0])} to ${signed(m.interval[1])}` : '—'}</td>
              <td>
                {m.baselineN}/{m.recentN}
              </td>
              <td>{screened.has(`${m.pitchType}:${m.metric}`) ? 'Review' : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function ScoutingCard({
  pitcher: p,
  window,
  onWindow,
  saved,
  onSave,
  onMethod,
  generatedAt,
  onToast,
}: Props) {
  const [pitch, setPitch] = useState('all');
  const eligible = p.status !== 'insufficient';
  return (
    <article className="scouting-card" aria-label={`${p.name} scouting report`}>
      <div className="report-header">
        <div className="report-top">
          <div>
            <div className="report-kicker">
              SCOUTING CARD <span /> {p.team || 'MLB'}
            </div>
            <h2>{p.name}</h2>
            <p className="pitcher-subline">
              {p.throws === 'L'
                ? 'Left-handed pitcher'
                : p.throws === 'R'
                  ? 'Right-handed pitcher'
                  : 'Pitcher'}{' '}
              <span>•</span> {p.arsenal.length}-pitch arsenal
            </p>
          </div>
          <div className="report-actions">
            <button
              className={saved ? 'saved' : ''}
              aria-pressed={saved}
              aria-label={`${saved ? 'Remove from' : 'Add to'} watchlist`}
              onClick={onSave}
            >
              <span aria-hidden="true">{saved ? '★' : '☆'}</span>
            </button>
            <button
              onClick={() => {
                exportScoutingCard(p, generatedAt, window);
                onToast('Scouting card exported.');
              }}
            >
              <span aria-hidden="true">↓</span> <span className="export-label">Export card</span>
            </button>
          </div>
        </div>
        <div className="report-period">
          <p>
            <b>Recent</b> {dateRange(p.recentStart, p.recentEnd)} · {count(p.recentCount)} pitches ·{' '}
            {p.recentAppearances} appearances
            <br />
            <b>Baseline</b> {dateRange(p.baselineStart, p.baselineEnd)} · {count(p.baselineCount)}{' '}
            pitches
          </p>
          <div className="window-selector" role="group" aria-label="Recent pitch window">
            {(['100', '200'] as const).map((w) => (
              <button
                key={w}
                onClick={() => onWindow(w)}
                className={w === window ? 'active' : ''}
                aria-pressed={w === window}
              >
                Last {w}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="report-body">
        <section aria-labelledby="signals-title">
          <div className="section-title">
            <h3 id="signals-title">What’s changed</h3>
            <span className={`review-badge ${p.alerts.length ? '' : 'green'}`}>
              {!eligible
                ? 'MORE DATA NEEDED'
                : p.alerts.length
                  ? `${p.alerts.length} SIGNAL${p.alerts.length === 1 ? '' : 'S'} TO REVIEW`
                  : 'NO QUALIFYING SIGNALS'}
            </span>
          </div>
          {p.alerts.length ? (
            <div className="signal-grid">
              {p.alerts.slice(0, 3).map((a) => (
                <SignalCard key={`${a.pitchType}:${a.metric}`} signal={a} />
              ))}
            </div>
          ) : (
            <div className="inline-neutral">
              {eligible
                ? 'The recent window looks broadly consistent with this pitcher’s baseline under the current screening rules.'
                : 'The recent or baseline window is too small to screen for changes.'}
            </div>
          )}
          <div className="scout-note">
            <span className="note-icon" aria-hidden="true">
              ↳
            </span>
            <p>
              <b>Scouting takeaway.</b> {takeaway(p)}
            </p>
          </div>
        </section>
        <div className="status-line">
          {p.warnings.map((warning) => (
            <p key={warning}>{warning}</p>
          ))}
        </div>
        <section className="chart-section" aria-labelledby="chart-title">
          <div className="section-title">
            <h3 id="chart-title">The shape of the change</h3>
            <span>CATCHER’S PERSPECTIVE</span>
          </div>
          <div className="chart-toolbar">
            <span className="filter-label">Pitch type</span>
            <div className="pitch-filter" role="group" aria-label="Filter charts by pitch type">
              <button
                onClick={() => setPitch('all')}
                className={pitch === 'all' ? 'active' : ''}
                aria-pressed={pitch === 'all'}
              >
                All pitches
              </button>
              {p.arsenal.map((a) => (
                <button
                  key={a.pitchType}
                  onClick={() => setPitch(a.pitchType)}
                  className={pitch === a.pitchType ? 'active' : ''}
                  aria-pressed={pitch === a.pitchType}
                >
                  <PitchDot type={a.pitchType} />
                  {pitchName(a.pitchType)}
                </button>
              ))}
            </div>
          </div>
          <div className="chart-grid">
            <div className="chart-panel">
              <div className="chart-panel-top">
                <h4>Pitch movement</h4>
                <span>INCHES</span>
              </div>
              <ScatterPlot pitcher={p} type={pitch} kind="movement" />
              <p className="plot-note">Induced movement; vertical break excludes gravity.</p>
            </div>
            <div className="chart-panel">
              <div className="chart-panel-top">
                <h4>Pitch location</h4>
                <span>FEET</span>
              </div>
              <ScatterPlot pitcher={p} type={pitch} kind="location" />
              <p className="plot-note">Reference zone shown. Actual zone varies by batter.</p>
            </div>
          </div>
          <div className="chart-legend">
            <span>
              <i className="legend-outline" />
              Prior baseline
            </span>
            <span>
              <i className="legend-fill" />
              Recent window
            </span>
          </div>
        </section>
        <section className="arsenal-section" aria-labelledby="arsenal-title">
          <div className="section-title">
            <h3 id="arsenal-title">Arsenal breakdown</h3>
            <span>BASELINE → RECENT</span>
          </div>
          <ArsenalTable pitcher={p} />
        </section>
        <section className="timeline-wrap">
          <div className="section-title">
            <h3>Velocity by date</h3>
            <span>MEAN VELOCITY · MPH</span>
          </div>
          <div className="chart-panel timeline-panel">
            <VelocityTimeline pitcher={p} type={pitch} />
          </div>
          <p className="status-line">
            {pitch === 'all'
              ? 'Select a pitch type above to isolate its trend.'
              : `${pitchName(pitch)} only.`}{' '}
            Date means within the comparison windows; edge dates may include partial outings.
          </p>
        </section>
        <details className="details-toggle">
          <summary>See all {p.metrics.length} metric comparisons & uncertainty</summary>
          <p>
            Intervals are approximate 95% intervals for the difference. Correlated pitches and
            multiple comparisons make these exploratory screens, not confirmed discoveries. “Screen”
            indicates both the practical and uncertainty rules were met.
          </p>
          <MetricTable pitcher={p} />
        </details>
        <div className="method-inline">
          Two non-overlapping windows. Pitch-type comparisons need ≥50 baseline and ≥20 recent
          observations; rate denominators vary by metric. Review video, opponents and subsequent
          outings before changing a game plan.{' '}
          <button className="text-button" onClick={onMethod}>
            Read the methodology ↗
          </button>
        </div>
      </div>
    </article>
  );
}

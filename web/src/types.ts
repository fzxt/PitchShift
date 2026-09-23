export type WindowSize = '100' | '200';
export type PitchType = string;
export interface Comparison {
  pitchType: PitchType; pitchName: string; metric: string; label: string;
  unit: string; baseline: number; recent: number; delta: number;
  baselineN: number; recentN: number; score: number;
  interval: [number, number]; practicalThreshold: number; interpretation?: string;
}
export interface ArsenalPitch {
  pitchType: PitchType; name: string; color: string;
  baselineCount: number; recentCount: number; baselineUsage: number; recentUsage: number;
  baselineVelocity: number | null; recentVelocity: number | null;
}
export interface PitchPoint { type: PitchType; x: number | null; z: number | null; px: number | null; pz: number | null }
export interface Outing { date: string; pitchType: PitchType; velocity: number; count: number }
export interface Pitcher {
  id: number; name: string; team: string; throws: string;
  recentCount: number; baselineCount: number;
  baselineStart: string; baselineEnd: string; recentStart: string; recentEnd: string;
  status: 'review' | 'stable' | 'insufficient'; alerts: Comparison[];
  arsenal: ArsenalPitch[]; metrics: Comparison[];
  points: { baseline: PitchPoint[]; recent: PitchPoint[] }; timeline: Outing[];
}
export interface Report {
  schemaVersion: 1; generatedAt: string;
  source: { dataStart?: string; dataEnd?: string; pitchCount?: number; pitcherCount?: number; retrievedAt?: string; notice?: string; [key: string]: unknown };
  windows: Record<WindowSize, { pitchers: Pitcher[] }>;
}

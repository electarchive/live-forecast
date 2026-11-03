type Band = { low: number; mid: number; high: number };
type Race = {
  state: string;
  counts: Array<{ unitId: string; at: string; votes: Array<number> }>;
  baseline: Array<{ unitId: string; turnout: number; shares: Array<number>; expected?: number }>;
};
type Estimate = {
  leader: string | null;
  status: string;
  winProbability: Record<string, number>;
  margin: Band;
  shareIn: Band;
  expectedTotal: Band;
};

const Z80 = 1.2815515655446004;
const MIN_UNITS = 3;
const WIDE = process.env.BASELINE === "wide";

function phi(x: number): number {
  const z = Math.abs(x) / Math.SQRT2;
  const t = 1 / (1 + 0.5 * z);
  const tail =
    t *
    Math.exp(
      -z * z -
        1.26551223 +
        t *
          (1.00002368 +
            t *
              (0.37409196 +
                t * (0.09678418 + t * (-0.18628806 + t * (0.27886807 + t * (-1.13520398 + t * (1.48851587 + t * (-0.82215223 + t * 0.17087277)))))))),
    );
  return x >= 0 ? 1 - tail / 2 : tail / 2;
}

export function estimate({ race, at }: { race: Race; at: string | null }): Estimate {
  const latest = new Map<string, Array<number>>();
  for (const count of race.counts) {
    if (at != null && count.at > at) continue;
    latest.set(count.unitId, count.votes);
  }
  const units = race.baseline.map((unit) => {
    const votes = latest.get(unit.unitId) ?? [0, 0, 0];
    const n = votes[0]! + votes[1]! + votes[2]!;
    const expected = unit.expected ?? unit.turnout;
    return {
      lead: votes[0]! - votes[1]!,
      n,
      past: unit.shares[0]! - unit.shares[1]!,
      left: Math.max(0, expected - n),
    };
  });
  const seen = units.filter((unit) => unit.n > 0);
  let counted = 0;
  let lead = 0;
  let total = 0;
  for (const unit of units) {
    counted += unit.n;
    lead += unit.lead;
    total += unit.n + unit.left;
  }
  const empty: Band = { low: 0, mid: 0, high: 0 };
  if (seen.length < Math.min(MIN_UNITS, units.length) || total <= 0) {
    return { leader: null, status: "too-early", winProbability: {}, margin: empty, shareIn: empty, expectedTotal: empty };
  }
  let sw = 0;
  let swx = 0;
  let swy = 0;
  let swxx = 0;
  let swxy = 0;
  for (const unit of seen) {
    const w = unit.n;
    const y = unit.lead / unit.n;
    sw += w;
    swx += w * unit.past;
    swy += w * y;
    swxx += w * unit.past * unit.past;
    swxy += w * unit.past * y;
  }
  const det = sw * swxx - swx * swx;
  const flat = seen.length < 3 || det <= 1e-12 * sw * sw;
  const slope = flat ? 1 : (sw * swxy - swx * swy) / det;
  const intercept = (swy - slope * swx) / sw;
  let squares = 0;
  for (const unit of seen) {
    const residual = unit.lead / unit.n - intercept - slope * unit.past;
    squares += residual * residual;
  }
  const sigma2 = squares / Math.max(1, seen.length - (flat ? 1 : 2));
  const a11 = sw;
  const a12 = swx;
  const a22 = swxx;
  let b11 = 0;
  let b12 = 0;
  let b22 = 0;
  for (const unit of seen) {
    const w2 = unit.n * unit.n;
    b11 += w2;
    b12 += w2 * unit.past;
    b22 += w2 * unit.past * unit.past;
  }
  const i11 = flat ? 1 / a11 : a22 / det;
  const i12 = flat ? 0 : -a12 / det;
  const i22 = flat ? 0 : a11 / det;
  const m11 = i11 * b11 + i12 * b12;
  const m12 = i11 * b12 + i12 * b22;
  const m21 = i12 * b11 + i22 * b12;
  const m22 = i12 * b12 + i22 * b22;
  const c11 = sigma2 * (m11 * i11 + m12 * i12);
  const c12 = sigma2 * (m11 * i12 + m12 * i22);
  const c22 = sigma2 * (m21 * i12 + m22 * i22);
  let variance = 0;
  let g1 = 0;
  let g2 = 0;
  for (const unit of units) {
    if (unit.left <= 0) continue;
    if (unit.n > 0) {
      const share = unit.lead / unit.n;
      lead += unit.left * share;
      variance += unit.left * unit.left * (WIDE ? sigma2 : Math.max(0, 1 - share * share) / unit.n);
    } else {
      lead += unit.left * (intercept + slope * unit.past);
      variance += unit.left * unit.left * sigma2;
      g1 += unit.left;
      g2 += unit.left * unit.past;
    }
  }
  variance += g1 * g1 * c11 + 2 * g1 * g2 * c12 + g2 * g2 * c22;
  const margin = lead / total;
  const spread = Math.sqrt(Math.max(variance, 0)) / total;
  const pD = spread > 0 ? phi(margin / spread) : margin > 0 ? 1 : margin < 0 ? 0 : 0.5;
  const leader = margin >= 0 ? "d" : "r";
  const sign = margin >= 0 ? 1 : -1;
  const share = counted / total;
  return {
    leader,
    status: "estimating",
    winProbability: { d: pD, r: 1 - pD },
    margin: { low: sign * margin - Z80 * spread, mid: sign * margin, high: sign * margin + Z80 * spread },
    shareIn: { low: share, mid: share, high: share },
    expectedTotal: { low: total, mid: total, high: total },
  };
}

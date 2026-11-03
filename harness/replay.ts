import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

type Band = { low: number; mid: number; high: number };
type Votes = [number, number, number];
type Row = [string, number, number, number];
type Count = { unitId: string; at: string; votes: Array<number>; reporting: null; expected: null };
type Frame = { at: string; totals: Array<number>; reporting: null; expected: null };
type Race = {
  id: string;
  slug: string;
  title: string;
  office: string;
  state: string;
  district: null;
  options: typeof options;
  units: Array<{ id: string; areaId: null; name: string; scheme: string; parentId: null }>;
  frames: Array<Frame>;
  counts: Array<Count>;
  baseline: Array<{ unitId: string; label: string; turnout: number; shares: Array<number>; expected?: number; traits?: Array<number> }>;
  certified: null;
  source: { publisher: string; url: null };
};
type Estimate = {
  leader: string | null;
  status: string;
  winProbability: Record<string, number>;
  margin: Band;
  shareIn: Band;
  expectedTotal: Band;
};
type Live = { estimate: (input: { race: Race; at: string | null }) => Estimate };

const root = resolve(import.meta.dirname, "..");
const main = resolve(process.env.MAIN ?? resolve(root, "../electionsarchive"));
const live = (await import(resolve(main, "packages/analytics/src/live.ts"))) as Live;
const args = new Map(process.argv.slice(2).map((arg) => arg.split("=") as [string, string]));
const sets = (args.get("sets") ?? "2020,2022,simulated").split(",");
const [part, parts] = (args.get("part") ?? "0/1").split("/").map(Number) as [number, number];
const out = resolve(args.get("out") ?? resolve(root, "outputs"));
const LATE: Record<string, number> = {
  ak: 0.4,
  az: 0.3,
  ca: 0.6,
  co: 0.1,
  dc: 0.1,
  fl: 0.01,
  hi: 0.05,
  il: 0.08,
  md: 0.2,
  nj: 0.12,
  nv: 0.25,
  ny: 0.08,
  or: 0.4,
  ut: 0.3,
  wa: 0.5,
};

const covariates: Record<string, Record<string, Array<number>>> = JSON.parse(
  readFileSync(resolve(root, "inputs/covariates.json"), "utf8"),
);
const options = [
  { id: "d", label: "D", person: null, photo: null, party: { id: "d", name: "D", short: "D", color: "" }, isWriteIn: false, isIncumbent: false },
  { id: "r", label: "R", person: null, photo: null, party: { id: "r", name: "R", short: "R", color: "" }, isWriteIn: false, isIncumbent: false },
  { id: "o", label: "O", person: null, photo: null, party: null, isWriteIn: false, isIncumbent: false },
];
const rows: Array<string> = [];

function score(set: string, race: Race, at: string, first: string, share: number, truth: number, total: number) {
  const est = live.estimate({ race, at });
  if (est.leader == null) return;
  const sign = est.leader === "d" ? 1 : est.leader === "r" ? -1 : 0;
  if (sign === 0) return;
  const pD = est.winProbability["d"] ?? (est.winProbability["r"] != null ? 1 - est.winProbability["r"] : 0.5);
  rows.push(
    JSON.stringify({
      set,
      race: race.id,
      at,
      minutes: (Date.parse(at) - Date.parse(first)) / 60_000,
      share,
      sin: est.shareIn.mid,
      status: est.status,
      pD,
      mid: sign * est.margin.mid,
      lo: sign > 0 ? est.margin.low : -est.margin.high,
      hi: sign > 0 ? est.margin.high : -est.margin.low,
      tmid: est.expectedTotal.mid,
      tlo: est.expectedTotal.low,
      thi: est.expectedTotal.high,
      truth,
      total,
    }),
  );
}

function real(year: number) {
  const data: Record<
    string,
    {
      st?: string;
      seat?: string;
      base: Array<Row>;
      expected?: Record<string, number>;
      snaps: Array<{ at: string; counties: Record<string, Votes> }>;
      truth: { margin: number; total: number };
    }
  > = JSON.parse(readFileSync(resolve(root, `frames/${year}.json`), "utf8"));
  let index = 0;
  for (const [key, s] of Object.entries(data)) {
    index += 1;
    if (index % parts !== part) continue;
    const st = s.st ?? key;
    const counts: Array<Count> = [];
    const frames: Array<Frame> = [];
    const last = new Map<string, string>();
    const ids = new Set<string>(s.base.map((row) => row[0]));
    for (const snap of s.snaps) {
      const totals = [0, 0, 0];
      for (const [fips, votes] of Object.entries(snap.counties)) {
        ids.add(fips);
        for (let i = 0; i < 3; i += 1) totals[i]! += votes[i]!;
        const sig = votes.join(",");
        if (last.get(fips) !== sig && votes[0] + votes[1] + votes[2] > 0) {
          counts.push({ unitId: fips, at: snap.at, votes, reporting: null, expected: null });
          last.set(fips, sig);
        }
      }
      frames.push({ at: snap.at, totals, reporting: null, expected: null });
    }
    const race: Race = {
      id: `real${year % 100}/${key}`,
      slug: `us/${st}/${year}/${s.seat ?? "president"}`,
      title: key,
      office: "other",
      state: st,
      district: null,
      options,
      units: [...ids].map((id) => ({ id, areaId: null, name: id, scheme: "us.county", parentId: null })),
      frames,
      counts,
      baseline: s.base
        .filter((row) => row[3] > 0)
        .map(([code, d, r, t]) => {
          const trait = covariates["2019"]![code] ?? covariates["2012"]![code];
          return {
            unitId: code,
            label: code,
            turnout: t,
            shares: [d / t, r / t, 0],
            ...(s.expected?.[code] != null ? { expected: s.expected[code] } : {}),
            ...(year !== 2020 && trait != null ? { traits: trait.slice(0, 4) } : {}),
          };
        }),
      certified: null,
      source: { publisher: "", url: null },
    };
    for (const frame of frames) {
      const counted = frame.totals[0]! + frame.totals[1]! + frame.totals[2]!;
      const share = counted / s.truth.total;
      if (share < 0.05) continue;
      score(String(year), race, frame.at, frames[0]!.at, share, s.truth.margin, s.truth.total);
    }
  }
}

function simulated() {
  const data: Record<string, Array<Row>> = JSON.parse(readFileSync(resolve(root, "inputs/counties.json"), "utf8"));
  const traitsOf = (code: string, year: number) => {
    const row = year <= 2016 ? covariates["2012"]![code] : (covariates["2019"]![code] ?? covariates["2012"]![code]);
    return row == null ? undefined : row.slice(0, 4);
  };
  const rng = (seed: number) => {
    let s = seed >>> 0;
    return () => {
      s = (s + 0x6d2b79f5) >>> 0;
      let t = Math.imul(s ^ (s >>> 15), 1 | s);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  };
  const normal = (r: () => number) => Math.sqrt(-2 * Math.log(Math.max(r(), 1e-12))) * Math.cos(2 * Math.PI * r());
  const expo = (r: () => number, mean: number) => -Math.log(Math.max(r(), 1e-12)) * mean;
  const total = (rows: Array<Row>, i: 1 | 2 | 3) => {
    let s = 0;
    for (const row of rows) s += row[i];
    return s;
  };
  const byState = new Map<string, Map<number, Array<{ seat: string; rows: Array<Row> }>>>();
  for (const [path, rows] of Object.entries(data)) {
    const m = /^us\/(..)\/(\d{4})-[\d-]+-general\/(.*)$/u.exec(path);
    if (m == null) continue;
    const [, st, yr, seat] = m;
    const years = byState.get(st!) ?? new Map();
    byState.set(st!, years);
    const list = years.get(Number(yr)) ?? [];
    years.set(Number(yr), list);
    list.push({ seat: seat!, rows });
  }
  const turnoutBy = (st: string, year: number) => {
    const found = new Map<string, number>();
    for (const { seat, rows } of byState.get(st)?.get(year) ?? []) {
      if (seat.startsWith("house")) continue;
      for (const [code, , , t] of rows) found.set(code, Math.max(found.get(code) ?? 0, t));
    }
    return found;
  };
  const president = (st: string, year: number) => byState.get(st)?.get(year)?.find((c) => c.seat === "president")?.rows ?? null;
  type Case = { path: string; st: string; year: number; rows: Array<Row>; base: Array<Row>; expected: Map<string, number> };
  const cases: Array<Case> = [];
  for (const [st, ys] of [...byState].toSorted((x, y) => x[0].localeCompare(y[0]))) {
    if (st === "pr" || st === "dc" || st === "ak") continue;
    for (const [year, list] of [...ys].toSorted((x, y) => x[0] - y[0])) {
      if (year < 2012 || year > 2024) continue;
      for (const { seat, rows } of list.toSorted((x, y) => x.seat.localeCompare(y.seat))) {
        if (!/^(president|senate|senate-special|governor)$/u.test(seat)) continue;
        const d = total(rows, 1);
        const r = total(rows, 2);
        const t = total(rows, 3);
        if (d < 0.2 * t || r < 0.2 * t || d + r < 0.75 * t || rows.length < 3) continue;
        let p = year - 1;
        while (p % 4 !== 0) p -= 1;
        if (seat === "president") p = year - 4;
        const prior = president(st, p);
        if (prior == null) continue;
        const expected = new Map<string, number>();
        if (year % 4 !== 0) {
          const now = turnoutBy(st, year - 4);
          const then = turnoutBy(st, p - 4);
          let a = 0;
          let b = 0;
          for (const [code, v] of now) {
            if (then.has(code)) {
              a += v;
              b += then.get(code)!;
            }
          }
          const stateRatio = b > 0 ? a / b : 0.75;
          for (const [code, , , t] of prior) {
            const x = now.get(code);
            const y = then.get(code);
            const ratio = x != null && y != null && y > 0 ? x / y : stateRatio;
            expected.set(code, t * Math.max(0.3, Math.min(1.6, ratio)));
          }
        }
        cases.push({ path: `us/${st}/${year}/${seat}`, st, year, rows, base: prior, expected });
      }
    }
  }
  const mailGap = (year: number, r: () => number) =>
    year >= 2024 ? 0.12 + 0.06 * normal(r) : year >= 2022 ? 0.18 + 0.08 * normal(r) : year >= 2020 ? 0.3 + 0.08 * normal(r) : 0.03 + 0.06 * normal(r);
  const channelShares = (year: number, r: () => number) => {
    let ed: number;
    let ip: number;
    if (year === 2020) {
      ed = 0.25 + 0.15 * r();
      ip = 0.15 + 0.25 * r();
    } else if (year >= 2022) {
      ed = 0.4 + 0.2 * r();
      ip = 0.1 + 0.25 * r();
    } else {
      ed = 0.6 + 0.25 * r();
      ip = 0.05 + 0.15 * r();
    }
    const mail = Math.max(0.03, 1 - ed - ip);
    const all = ed + ip + mail;
    return [ed / all, ip / all, mail / all];
  };
  const CHECK = [0.03, 0.1, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95];
  for (const [index, c] of cases.entries()) {
    if (index % parts !== part) continue;
    const r = rng(Number.parseInt(c.path.replace(/\W/gu, "").slice(-12), 36));
    const gap = mailGap(c.year, r);
    const shares = channelShares(c.year, r);
    const u = r();
    const scenarioDraw = r();
    const scenario = scenarioDraw < 0.45 ? "early" : scenarioDraw < 0.7 ? "ed" : "mixed";
    const lateShareLam = (LATE[c.st] ?? 0.0375) * (0.4 + 1.2 * r());
    const lateShare = lateShareLam / (1 + lateShareLam);
    const lateGap = 0.1 * normal(r);
    const chunks: Array<{ unit: string; t: number; d: number; r: number; o: number }> = [];
    for (const [code, d, rr, t0] of c.rows) {
      if (t0 <= 0) continue;
      const oth = Math.max(0, t0 - d - rr);
      const m = (d - rr) / t0;
      const othShare = oth / t0;
      const local = shares.map((s) => Math.max(0.02, s * (1 + 0.25 * normal(r))));
      const ls = local[0]! + local[1]! + local[2]!;
      const sh = local.map((s) => s / ls);
      const g = gap * (1 + 0.3 * normal(r));
      const oEd = -g * (sh[1]! * u + sh[2]!);
      const offsets = [oEd, oEd + g * u, oEd + g];
      const piecesOf = sh.map((s, i) => {
        const v = s * t0;
        const lim = 0.98 * (1 - othShare);
        const gm = Math.max(-lim, Math.min(lim, m + offsets[i]!));
        return { v, d: (v * (1 - othShare + gm)) / 2, r: (v * (1 - othShare - gm)) / 2, o: v * othShare };
      });
      let sd = 0;
      let sr = 0;
      for (const p of piecesOf) {
        sd += p.d;
        sr += p.r;
      }
      for (const p of piecesOf) {
        p.d *= sd > 0 ? d / sd : 0;
        p.r *= sr > 0 ? rr / sr : 0;
      }
      const late = { d: 0, r: 0, o: 0 };
      {
        const mail = piecesOf[2]!;
        const mt = mail.d + mail.r + mail.o;
        const lv = Math.min(0.8 * mt, lateShare * t0);
        const lm = Math.max(-0.95, Math.min(0.95, (mail.d - mail.r) / Math.max(mt, 1) + lateGap));
        const lo = lv * othShare;
        const ld = Math.min(mail.d, ((lv - lo) * (1 + lm)) / 2);
        const lr = Math.min(mail.r, lv - lo - ld);
        late.d = ld;
        late.r = lr;
        late.o = lo;
        mail.d -= ld;
        mail.r -= lr;
        mail.o -= lo;
      }
      const k = Math.max(1, Math.min(8, Math.round(Math.log2(t0 / 3000))));
      const size = Math.log10(t0);
      let t = expo(r, 15) + 10 * Math.max(0, size - 4) + 5 * r();
      const order = scenario === "early" ? [2, 1, 0] : scenario === "ed" ? [0, 1, 2] : r() < 0.5 ? [2, 1, 0] : [0, 2, 1];
      for (const ch of order) {
        const p = piecesOf[ch]!;
        const pieces = ch === 0 ? k : Math.max(1, Math.ceil(k / 2));
        const weights = Array.from({ length: pieces }, () => 0.3 + r());
        const offs = weights.map(() => 0.06 * normal(r));
        let ws = 0;
        let mo = 0;
        for (const [i, w] of weights.entries()) {
          ws += w;
          mo += w * offs[i]!;
        }
        mo /= ws;
        const v = p.d + p.r + p.o;
        const pm = v > 0 ? (p.d - p.r) / v : 0;
        const po = v > 0 ? p.o / v : 0;
        let leftD = p.d;
        let leftR = p.r;
        let leftO = p.o;
        for (const [i, w] of weights.entries()) {
          const pv = (v * w) / ws;
          const lim = 0.98 * (1 - po);
          const gm = Math.max(-lim, Math.min(lim, pm + offs[i]! - mo));
          let cd = i === pieces - 1 ? leftD : Math.min(leftD, (pv * (1 - po + gm)) / 2);
          let cr = i === pieces - 1 ? leftR : Math.min(leftR, (pv * (1 - po - gm)) / 2);
          let co = i === pieces - 1 ? leftO : Math.min(leftO, pv * po);
          cd = Math.max(0, cd);
          cr = Math.max(0, cr);
          co = Math.max(0, co);
          leftD -= cd;
          leftR -= cr;
          leftO -= co;
          t += expo(r, 8 * Math.max(1, size - 3));
          chunks.push({ unit: code, t, d: cd, r: cr, o: co });
        }
      }
      chunks.push({ unit: code, t: 1e6 + r(), d: late.d, r: late.r, o: late.o });
    }
    chunks.sort((x, y) => x.t - y.t);
    const all = total(c.rows, 3);
    const truth = (total(c.rows, 1) - total(c.rows, 2)) / all;
    const iso = (minutes: number) => new Date(Date.UTC(2030, 0, 1, 0, 0) + minutes * 60_000).toISOString();
    const cum = new Map<string, [number, number, number]>();
    const counts: Array<Count> = [];
    const frames: Array<Frame> = [];
    let counted = 0;
    let nextFrame = 0.01;
    let qi = 0;
    const checkpoints: Array<{ q: number; at: string }> = [];
    let dirty = new Set<string>();
    for (const ch of chunks) {
      if (ch.t >= 1e6) break;
      const v = cum.get(ch.unit) ?? [0, 0, 0];
      v[0] += ch.d;
      v[1] += ch.r;
      v[2] += ch.o;
      cum.set(ch.unit, v);
      dirty.add(ch.unit);
      counted += ch.d + ch.r + ch.o;
      const share = counted / all;
      if (share >= nextFrame || (qi < CHECK.length && share >= CHECK[qi]!)) {
        const at = iso(ch.t);
        for (const unit of dirty) {
          counts.push({ unitId: unit, at, votes: cum.get(unit)!.map(Math.round), reporting: null, expected: null });
        }
        dirty = new Set();
        const totals = [0, 0, 0];
        for (const x of cum.values()) for (let i = 0; i < 3; i += 1) totals[i]! += x[i]!;
        frames.push({ at, totals: totals.map(Math.round), reporting: null, expected: null });
        while (share >= nextFrame) nextFrame += 0.01;
        while (qi < CHECK.length && share >= CHECK[qi]!) {
          checkpoints.push({ q: CHECK[qi]!, at });
          qi += 1;
        }
      }
    }
    const race: Race = {
      id: `${c.path}#0`,
      slug: c.path,
      title: c.path,
      office: "senate",
      state: c.st,
      district: null,
      options,
      units: c.rows.map(([code]) => ({ id: code, areaId: null, name: code, scheme: "us.county", parentId: null })),
      frames,
      counts,
      baseline: c.base
        .filter((x) => x[3] > 0)
        .map(([code, d, rr, t]) => ({
          unitId: code,
          label: code,
          turnout: t,
          shares: [d / t, rr / t, 0],
          ...(c.expected.has(code) ? { expected: c.expected.get(code)! } : {}),
          ...(traitsOf(code, c.year) != null ? { traits: traitsOf(code, c.year)! } : {}),
        })),
      certified: null,
      source: { publisher: "", url: null },
    };
    for (const { q, at } of checkpoints) {
      score(c.year % 4 === 0 ? "presidential" : "midterm", race, at, frames[0]!.at, q, truth, all);
    }
  }
}

for (const set of sets) {
  if (set === "2020") real(2020);
  if (set === "2022") real(2022);
  if (set === "simulated") simulated();
}
mkdirSync(out, { recursive: true });
writeFileSync(resolve(out, parts > 1 ? `estimates.${part}.jsonl` : "estimates.jsonl"), rows.length > 0 ? `${rows.join("\n")}\n` : "");

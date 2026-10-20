import {
  ORBIT_GAP,
  ORBIT_TIERS,
  TIER_OF,
  type NodeCategory,
  type Tier,
} from './graphStyle';

const CORE_RADIUS = 28;

export interface Orbit {
  label: string;
  radius: number;
  dashed: boolean;
}

export interface OrbitLayout {
  /** Only tiers that hold nodes; inner to outer. */
  orbits: Orbit[];
  radiusOf: (category: NodeCategory) => number;
}

/**
 * One orbit per non-empty tier. An orbit grows until its nodes fit around
 * it, and every orbit sits at least `ORBIT_GAP` outside the one before.
 */
export function layoutOrbits(categories: readonly NodeCategory[]): OrbitLayout {
  const counts = new Map<Tier, number>();
  for (const category of categories) {
    const tier = TIER_OF[category];
    counts.set(tier, (counts.get(tier) ?? 0) + 1);
  }
  // Several seeds share a small inner circle instead of piling up at 0, 0.
  const core = (counts.get('core') ?? 0) > 1 ? CORE_RADIUS : 0;
  const radii = new Map<Tier, number>([['core', core]]);
  const orbits: Orbit[] = [];
  let previous = core;
  for (const { tier, label, minRadius, spacing, dashed } of ORBIT_TIERS) {
    const count = counts.get(tier) ?? 0;
    if (count === 0) continue;
    const radius = Math.max(
      minRadius,
      previous + ORBIT_GAP,
      (count * spacing) / (2 * Math.PI),
    );
    radii.set(tier, radius);
    orbits.push({ label, radius, dashed });
    previous = radius;
  }
  return {
    orbits,
    radiusOf: (category) => radii.get(TIER_OF[category]) ?? 0,
  };
}

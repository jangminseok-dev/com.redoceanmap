// 매물대(가격대별 거래량 분포) 계산 — stock CandleChart용.
//
// "과거에 어느 가격대에서 거래가 밀집했나"를 보여주는 팩트 지표다. 지지/저항 판정은
// 하지 않는다(검증 안 된 주장 단정 금지 — 화면 문구도 "거래 밀집 구간"으로 통일).

export type VolumeProfileBin = { low: number; high: number; volume: number };

export type VolumeProfile = {
  bins: VolumeProfileBin[];
  maxVolume: number;
  pocIndex: number; // 최다 거래 구간(Point of Control)
};

// 차트 페인 높이 ~340px 기준 한 칸 14px — 이보다 잘게 나누면 칸이 시각적으로 뭉개진다
export const VOLUME_PROFILE_BINS = 24;

// 표본이 이보다 적으면 분포가 아니라 노이즈다 — 그리지 않는다
const MIN_BARS = 5;

/**
 * 봉 목록 → 가격 구간별 거래량 분포.
 *
 * 봉 내부의 체결 분포는 알 수 없으므로 대표가(고+저+종)/3 한 점에 거래량을 놓는
 * 근사를 쓴다. 고저 범위를 여러 칸에 나눠 담는 배분이 더 정밀해 보이지만,
 * "봉 안에서 균등하게 거래됐다"는 근거 없는 가정이 하나 더 들어갈 뿐이다.
 */
export function computeVolumeProfile(
  bars: { high: number; low: number; close: number; volume: number }[],
  binCount: number = VOLUME_PROFILE_BINS,
): VolumeProfile | null {
  if (bars.length < MIN_BARS) return null;
  let min = Infinity;
  let max = -Infinity;
  for (const b of bars) {
    if (b.low < min) min = b.low;
    if (b.high > max) max = b.high;
  }
  if (!(max > min)) return null;

  const size = (max - min) / binCount;
  const volumes = new Array<number>(binCount).fill(0);
  for (const b of bars) {
    const typical = (b.high + b.low + b.close) / 3;
    const idx = Math.min(binCount - 1, Math.max(0, Math.floor((typical - min) / size)));
    volumes[idx] += b.volume;
  }

  let pocIndex = 0;
  for (let i = 1; i < binCount; i++) {
    if (volumes[i] > volumes[pocIndex]) pocIndex = i;
  }
  if (volumes[pocIndex] <= 0) return null;

  return {
    bins: volumes.map((v, i) => ({
      low: min + i * size,
      high: min + (i + 1) * size,
      volume: v,
    })),
    maxVolume: volumes[pocIndex],
    pocIndex,
  };
}

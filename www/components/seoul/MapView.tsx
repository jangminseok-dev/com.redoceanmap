"use client";

import { useEffect, useRef } from "react";
import { Minus, Plus } from "lucide-react";

declare global {
  interface Window {
    kakao: any;
  }
}

const KAKAO_SDK_URL = `//dapi.kakao.com/v2/maps/sdk.js?appkey=${process.env.NEXT_PUBLIC_KAKAO_MAP_KEY}&autoload=false`;

// 지도에 찍는 데 필요한 최소 형태 — Area(추천 카드)와 상권 조회 응답 모두 수용
export type MapPin = { id: string; lat: number; lng: number };

type Props = {
  areas: MapPin[];
  selectedId: string | null;
  onSelect: (id: string) => void;
};

function makePinContent(selected: boolean): string {
  const fill = selected ? "#7A1515" : "#991B1B";
  const w = selected ? 34 : 26;
  const h = selected ? 44 : 33;
  const shadow = selected
    ? "filter:drop-shadow(0 3px 6px rgba(0,0,0,0.35))"
    : "filter:drop-shadow(0 1px 3px rgba(0,0,0,0.25))";
  return `<div style="cursor:pointer;${shadow}">
    <svg width="${w}" height="${h}" viewBox="0 0 16 20" aria-hidden="true">
      <path d="M8 0C3.6 0 0 3.6 0 8c0 6 8 12 8 12s8-6 8-12c0-4.4-3.6-8-8-8z" fill="${fill}"/>
      <circle cx="8" cy="8" r="2.5" fill="#FFFFFF"/>
    </svg>
  </div>`;
}

export default function MapView({ areas, selectedId, onSelect }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const overlaysRef = useRef<{ id: string; overlay: any }[]>([]);
  const areasRef = useRef(areas);
  const onSelectRef = useRef(onSelect);
  const selectedIdRef = useRef(selectedId);

  areasRef.current = areas;
  onSelectRef.current = onSelect;
  selectedIdRef.current = selectedId;

  function placeMarkers(map: any, list: MapPin[], currentSelectedId: string | null) {
    overlaysRef.current.forEach(({ overlay }) => overlay.setMap(null));
    overlaysRef.current = [];

    list.forEach((area) => {
      const pos = new window.kakao.maps.LatLng(area.lat, area.lng);
      const isSelected = area.id === currentSelectedId;

      const content = document.createElement("div");
      content.innerHTML = makePinContent(isSelected);
      content.addEventListener("click", () => onSelectRef.current(area.id));

      const overlay = new window.kakao.maps.CustomOverlay({
        position: pos,
        content,
        yAnchor: 1,
        map,
      });

      overlaysRef.current.push({ id: area.id, overlay });
    });
  }

  function initMap() {
    if (!containerRef.current || mapRef.current) return;
    const map = new window.kakao.maps.Map(containerRef.current, {
      center: new window.kakao.maps.LatLng(37.5445, 126.988),
      level: 7,
    });
    mapRef.current = map;
    placeMarkers(map, areasRef.current, selectedIdRef.current);

    const sel = areasRef.current.find((a) => a.id === selectedIdRef.current);
    if (sel) map.setCenter(new window.kakao.maps.LatLng(sel.lat, sel.lng));
  }

  useEffect(() => {
    const load = () => window.kakao.maps.load(initMap);

    if (window.kakao?.maps) { load(); return; }

    if (document.querySelector(`script[src*="dapi.kakao.com"]`)) {
      const id = setInterval(() => {
        if (window.kakao?.maps) { clearInterval(id); load(); }
      }, 100);
      return () => clearInterval(id);
    }

    const script = document.createElement("script");
    script.src = KAKAO_SDK_URL;
    script.async = true;
    script.onload = load;
    document.head.appendChild(script);
  }, []);

  useEffect(() => {
    if (!mapRef.current || areas.length === 0) return;
    placeMarkers(mapRef.current, areas, selectedIdRef.current);
  }, [areas]);

  // 컨테이너 크기 변화(모바일 탭 전환 등) 시 지도 재배치
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver(() => mapRef.current?.relayout());
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!mapRef.current) return;
    placeMarkers(mapRef.current, areasRef.current, selectedId);
    const area = areasRef.current.find((a) => a.id === selectedId);
    if (area) mapRef.current.panTo(new window.kakao.maps.LatLng(area.lat, area.lng));
  }, [selectedId]);

  // 카카오맵은 level이 작을수록 확대다 — 버튼 라벨과 부호가 반대라는 걸 여기서 흡수한다
  const zoom = (delta: number) => {
    const map = mapRef.current;
    if (!map) return;
    map.setLevel(map.getLevel() + delta);
  };

  return (
    <div className="relative w-full h-full">
      <div ref={containerRef} className="w-full h-full" />

      {/* 지도 컨트롤 — 레퍼런스(네이버지도)의 우측 세로 스택. 지금 우리가 가진 조작은 줌뿐이다.
          테마·거리뷰·면적 같은 칸은 대응 기능이 없어 만들지 않는다(빈 버튼은 UI가 아니라 거짓말이다). */}
      <div className="absolute right-3 bottom-3 z-10 flex flex-col rounded-xl border border-border bg-surface shadow-sm overflow-hidden">
        <button
          type="button"
          onClick={() => zoom(-1)}
          aria-label="지도 확대"
          className="w-9 h-9 grid place-items-center text-foreground-muted hover:bg-accent hover:text-foreground transition-colors"
        >
          <Plus size={16} strokeWidth={2} />
        </button>
        <span className="h-px bg-border" aria-hidden />
        <button
          type="button"
          onClick={() => zoom(1)}
          aria-label="지도 축소"
          className="w-9 h-9 grid place-items-center text-foreground-muted hover:bg-accent hover:text-foreground transition-colors"
        >
          <Minus size={16} strokeWidth={2} />
        </button>
      </div>
    </div>
  );
}

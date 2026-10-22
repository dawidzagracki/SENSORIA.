"use client";

import "leaflet/dist/leaflet.css";
import { useEffect, useRef } from "react";
import type { Map as LeafletMap, Marker } from "leaflet";

import type { PickupPointSnapshot } from "@/components/cart/cart-types";

export type PickupMapHandle = { center: () => [number, number] | null };

type PickupMapProps = {
  points: PickupPointSnapshot[];
  activeCode: string | null;
  onActivate: (code: string) => void;
  onReady?: (handle: PickupMapHandle) => void;
};

type LocatedPoint = PickupPointSnapshot & {
  latitude: number;
  longitude: number;
};

function located(points: PickupPointSnapshot[]): LocatedPoint[] {
  return points.filter(
    (point): point is LocatedPoint =>
      typeof point.latitude === "number" && typeof point.longitude === "number",
  );
}

function markerHtml(code: string, active: boolean) {
  const tone = active ? "bg-ink text-surface" : "bg-accent-action text-surface";
  return `<span class="flex h-11 w-11 items-center justify-center rounded-pill border-2 border-surface text-caption font-bold shadow-subtle ${tone}">${active ? "✓" : "P"}</span><span class="sr-only">${code}</span>`;
}

export function PickupMap({
  points,
  activeCode,
  onActivate,
  onReady,
}: PickupMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const markersRef = useRef<Map<string, Marker>>(new Map());
  const leafletRef = useRef<typeof import("leaflet") | null>(null);
  const onActivateRef = useRef(onActivate);
  const onReadyRef = useRef(onReady);
  useEffect(() => {
    onActivateRef.current = onActivate;
    onReadyRef.current = onReady;
  });

  const items = located(points);
  const signature = items.map((point) => point.code).join("|");

  useEffect(() => {
    let cancelled = false;
    async function build() {
      const leaflet = await import("leaflet");
      if (cancelled || !containerRef.current) {
        return;
      }
      leafletRef.current = leaflet;
      mapRef.current?.remove();
      markersRef.current.clear();
      const map = leaflet.map(containerRef.current, { scrollWheelZoom: false });
      mapRef.current = map;
      const observer = new ResizeObserver(() => map.invalidateSize());
      observer.observe(containerRef.current);
      map.on("unload", () => observer.disconnect());
      leaflet
        .tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 19,
          attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        })
        .addTo(map);
      onReadyRef.current?.({
        center: () => {
          const c = map.getCenter();
          return [c.lat, c.lng];
        },
      });
      const bounds = leaflet.latLngBounds([]);
      for (const point of items) {
        const marker = leaflet
          .marker([point.latitude, point.longitude], {
            title: `${point.code} · ${point.street}, ${point.city}`,
            keyboard: true,
            icon: leaflet.divIcon({
              className: "",
              html: markerHtml(point.code, false),
              iconSize: [44, 44],
              iconAnchor: [22, 22],
            }),
          })
          .addTo(map);
        marker.on("click", () => onActivateRef.current(point.code));
        markersRef.current.set(point.code, marker);
        bounds.extend([point.latitude, point.longitude]);
      }
      if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [32, 32], maxZoom: 15 });
      } else {
        map.setView([52.1, 19.4], 6);
      }
    }
    void build();
    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
      markersRef.current.clear();
    };
    // Rebuild only when the result set changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature]);

  useEffect(() => {
    const leaflet = leafletRef.current;
    if (!leaflet) {
      return;
    }
    for (const [code, marker] of markersRef.current) {
      marker.setIcon(
        leaflet.divIcon({
          className: "",
          html: markerHtml(code, code === activeCode),
          iconSize: [44, 44],
          iconAnchor: [22, 22],
        }),
      );
      marker.setZIndexOffset(code === activeCode ? 1000 : 0);
    }
    const active = items.find((point) => point.code === activeCode);
    if (active && mapRef.current) {
      mapRef.current.panTo([active.latitude, active.longitude]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeCode, signature]);

  return (
    <div
      aria-label="Mapa Paczkomatów"
      className="relative z-0 h-72 w-full overflow-hidden rounded-card border border-border"
      data-testid="pickup-map"
      ref={containerRef}
      role="region"
    />
  );
}

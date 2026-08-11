'use client';

import { useEffect, useRef } from 'react';

interface MapViewProps {
  center?: [number, number];
  zoom?: number;
}

export default function MapView({ center = [50.8159, 7.1533], zoom = 12 }: MapViewProps) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<any>(null);

  useEffect(() => {
    if (!mapRef.current || mapInstance.current) return;

    const initMap = async () => {
      const L = (await import('leaflet')).default;

      const map = L.map(mapRef.current!, {
        center,
        zoom,
        zoomControl: true,
      });

      L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap &copy; CARTO',
        maxZoom: 19,
      }).addTo(map);

      const troisdorfMarker = L.marker(center, {
        icon: L.divIcon({
          className: '',
          html: `<div style="
            background: #e81e1e;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            border: 2px solid white;
            box-shadow: 0 0 10px rgba(232,30,30,0.5);
          "></div>`,
          iconSize: [12, 12],
          iconAnchor: [6, 6],
        }),
      }).addTo(map);
      troisdorfMarker.bindPopup('<b>DRK Troisdorf</b><br/>Zentrale');

      const wahnerHeide = L.polygon([
        [50.87, 7.12], [50.87, 7.18], [50.84, 7.20],
        [50.83, 7.18], [50.83, 7.13], [50.85, 7.11],
      ], {
        color: '#f97316',
        fillColor: '#f97316',
        fillOpacity: 0.1,
        weight: 2,
        dashArray: '5, 5',
      }).addTo(map);
      wahnerHeide.bindPopup('<b>Wahner Heide</b><br/>Waldbrand-Überwachungszone');

      mapInstance.current = map;
    };

    initMap();

    return () => {
      mapInstance.current?.remove();
      mapInstance.current = null;
    };
  }, []);

  return (
    <div
      ref={mapRef}
      className="w-full h-full min-h-[400px] rounded-lg"
      style={{ background: '#1e1e1e' }}
    />
  );
}

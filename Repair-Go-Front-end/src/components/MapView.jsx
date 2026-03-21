import { useEffect, useRef, useState, useCallback } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  Polyline,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Fix Leaflet default icon issue
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl:
    "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

// Custom icons
const technicianIcon = new L.DivIcon({
  className: "custom-marker",
  html: `<div style="
    background: linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%);
    width: 44px;
    height: 44px;
    border-radius: 50%;
    border: 3px solid white;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
  ">🛠️</div>`,
  iconSize: [44, 44],
  iconAnchor: [22, 22],
  popupAnchor: [0, -22],
});

const customerIcon = new L.DivIcon({
  className: "custom-marker",
  html: `<div style="
    background: linear-gradient(135deg, #10B981 0%, #059669 100%);
    width: 44px;
    height: 44px;
    border-radius: 50%;
    border: 3px solid white;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
  ">📍</div>`,
  iconSize: [44, 44],
  iconAnchor: [22, 22],
  popupAnchor: [0, -22],
});

const originIcon = new L.DivIcon({
  className: "custom-marker",
  html: `<div style="
    background: linear-gradient(135deg, #F59E0B 0%, #D97706 100%);
    width: 36px;
    height: 36px;
    border-radius: 50%;
    border: 3px solid white;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
  ">🧑</div>`,
  iconSize: [36, 36],
  iconAnchor: [18, 18],
  popupAnchor: [0, -18],
});

// Component to auto-fit bounds when markers change
function MapBoundsUpdater({ routeCoords, technicianPos, customerPos, autoCenter = true }) {
  const map = useMap();
  const hasSetBounds = useRef(false);

  useEffect(() => {
    if (!autoCenter) return;

    // Prefer fitting to route bounds if available
    if (routeCoords && routeCoords.length >= 2) {
      const bounds = L.latLngBounds(routeCoords);
      map.fitBounds(bounds, { padding: [60, 60], maxZoom: 16 });
      hasSetBounds.current = true;
      return;
    }

    const positions = [];
    if (technicianPos && technicianPos[0] && technicianPos[1]) {
      positions.push(technicianPos);
    }
    if (customerPos && customerPos[0] && customerPos[1]) {
      positions.push(customerPos);
    }

    if (positions.length >= 2 && !hasSetBounds.current) {
      const bounds = L.latLngBounds(positions);
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 16 });
      hasSetBounds.current = true;
    } else if (positions.length === 1) {
      map.setView(positions[0], 15);
    }
  }, [routeCoords, technicianPos, customerPos, autoCenter, map]);

  return null;
}

// ─── OSRM Route Hook ───────────────────────────────────────────────────────
function useOsrmRoute(origin, destination) {
  const [routeCoords, setRouteCoords] = useState(null);
  const [routeDistance, setRouteDistance] = useState(null); // km
  const [routeDuration, setRouteDuration] = useState(null); // minutes
  const lastFetch = useRef(0);
  const abortRef = useRef(null);

  const fetchRoute = useCallback(async () => {
    if (
      !origin || !destination ||
      !origin[0] || !origin[1] ||
      !destination[0] || !destination[1]
    ) {
      return;
    }

    // Throttle: at most once every 5 seconds
    const now = Date.now();
    if (now - lastFetch.current < 5000) return;
    lastFetch.current = now;

    // Abort any in-flight request
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const url =
        `https://router.project-osrm.org/route/v1/driving/` +
        `${origin[1]},${origin[0]};${destination[1]},${destination[0]}` +
        `?overview=full&geometries=geojson`;

      const res = await fetch(url, { signal: controller.signal });
      if (!res.ok) return;
      const data = await res.json();

      if (data.code === "Ok" && data.routes?.[0]) {
        const route = data.routes[0];
        // GeoJSON coordinates are [lng, lat] — flip to [lat, lng] for Leaflet
        const coords = route.geometry.coordinates.map(([lng, lat]) => [lat, lng]);
        setRouteCoords(coords);
        setRouteDistance(route.distance / 1000); // metres → km
        setRouteDuration(route.duration / 60);   // seconds → minutes
      }
    } catch {
      // Network error or aborted — keep previous route
    }
  }, [origin, destination]);

  // Fetch on mount and whenever positions change meaningfully
  useEffect(() => {
    fetchRoute();
  }, [
    // Round to ~100 m to avoid excessive re-fetches
    origin && Math.round(origin[0] * 1000),
    origin && Math.round(origin[1] * 1000),
    destination && Math.round(destination[0] * 1000),
    destination && Math.round(destination[1] * 1000),
  ]);

  return { routeCoords, routeDistance, routeDuration, refetchRoute: fetchRoute };
}

// Smooth marker movement animation
function AnimatedMarker({ position, icon, children }) {
  const markerRef = useRef(null);
  const prevPosition = useRef(position);

  useEffect(() => {
    if (markerRef.current && position && prevPosition.current) {
      const marker = markerRef.current;
      const start = prevPosition.current;
      const end = position;

      if (start[0] !== end[0] || start[1] !== end[1]) {
        // Simple animation - move marker smoothly
        const duration = 1000; // 1 second
        const startTime = Date.now();

        const animate = () => {
          const elapsed = Date.now() - startTime;
          const progress = Math.min(elapsed / duration, 1);

          // Ease out cubic
          const eased = 1 - Math.pow(1 - progress, 3);

          const lat = start[0] + (end[0] - start[0]) * eased;
          const lng = start[1] + (end[1] - start[1]) * eased;

          marker.setLatLng([lat, lng]);

          if (progress < 1) {
            requestAnimationFrame(animate);
          }
        };

        animate();
      }

      prevPosition.current = position;
    }
  }, [position]);

  return (
    <Marker ref={markerRef} position={position} icon={icon}>
      {children}
    </Marker>
  );
}

/**
 * MapView Component - Ola/Rapido style live tracking map
 *
 * @param {Object} props
 * @param {[number, number]} props.technicianPosition - [lat, lng] of technician
 * @param {[number, number]} props.customerPosition - [lat, lng] of customer/destination
 * @param {[number, number]} props.selfPosition - [lat, lng] of current user (for technician view)
 * @param {string} props.technicianName - Name to show in popup
 * @param {number} props.eta - Estimated time in minutes
 * @param {number} props.distance - Distance in km
 * @param {number} props.speed - Speed in km/h
 * @param {number} props.heading - Direction in degrees
 * @param {string} props.status - Current job status
 * @param {string} props.mode - "customer" or "technician"
 * @param {string} props.height - Map container height (default 350px)
 */
export default function MapView({
  technicianPosition,
  customerPosition,
  selfPosition,
  technicianName = "Technician",
  customerAddress = "Customer Location",
  eta,
  distance,
  speed,
  heading,
  status,
  mode = "customer",
  height = "350px",
}) {
  // Default center (if no positions provided)
  const defaultCenter = [12.9716, 77.5946]; // Bangalore

  // ─── OSRM Route ──────────────────────────────────────────────────────
  const routeOrigin = technicianPosition;
  const routeDest = customerPosition;

  const { routeCoords, routeDistance, routeDuration } = useOsrmRoute(
    routeOrigin,
    routeDest,
  );

  // Prefer OSRM values when available, fall back to props
  const displayEta = routeDuration ?? eta;
  const displayDistance = routeDistance ?? distance;

  // Active statuses where we show the route + ETA
  const showRoute = [
    "assigned",
    "accepted",
    "on_the_way",
    "in_progress",
  ].includes(status);

  // Determine map center
  const getCenter = () => {
    if (mode === "customer") {
      if (technicianPosition?.[0] && technicianPosition?.[1]) {
        return technicianPosition;
      }
      if (customerPosition?.[0] && customerPosition?.[1]) {
        return customerPosition;
      }
    } else {
      if (selfPosition?.[0] && selfPosition?.[1]) {
        return selfPosition;
      }
      if (customerPosition?.[0] && customerPosition?.[1]) {
        return customerPosition;
      }
    }
    return defaultCenter;
  };

  const center = getCenter();

  return (
    <div style={{ position: "relative" }}>
      {/* Status overlay */}
      <div
        style={{
          position: "absolute",
          top: "12px",
          left: "12px",
          right: "12px",
          zIndex: 1000,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          pointerEvents: "none",
        }}
      >
        {/* ETA Card — visible for all active statuses when we have data */}
        {displayEta !== undefined && showRoute && (
          <div
            style={{
              background: "white",
              borderRadius: "12px",
              padding: "12px 16px",
              boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
              pointerEvents: "auto",
            }}
          >
            <div
              style={{
                fontSize: "0.75rem",
                color: "#666",
                marginBottom: "2px",
              }}
            >
              {status === "on_the_way" ? "Arriving in" : "ETA"}
            </div>
            <div
              style={{
                fontSize: "1.5rem",
                fontWeight: "bold",
                color: "#1D4ED8",
              }}
            >
              {Math.round(displayEta)} min
            </div>
            {displayDistance !== undefined && (
              <div style={{ fontSize: "0.75rem", color: "#666" }}>
                {displayDistance.toFixed(1)} km away
              </div>
            )}
          </div>
        )}

        {/* Speed indicator */}
        {speed !== undefined && speed > 0 && (
          <div
            style={{
              background: "white",
              borderRadius: "12px",
              padding: "8px 12px",
              boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              pointerEvents: "auto",
            }}
          >
            <span style={{ fontSize: "1.1rem" }}>🚗</span>
            <span style={{ fontWeight: "600" }}>{Math.round(speed)} km/h</span>
          </div>
        )}
      </div>

      {/* Map Container */}
      <MapContainer
        center={center}
        zoom={15}
        style={{
          height: height,
          width: "100%",
          borderRadius: "12px",
          overflow: "hidden",
        }}
        scrollWheelZoom={true}
      >
        {/* OpenStreetMap tiles */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {/* Auto-fit bounds */}
        <MapBoundsUpdater
          routeCoords={showRoute ? routeCoords : null}
          technicianPos={technicianPosition}
          customerPos={customerPosition}
          autoCenter={true}
        />

        {/* OSRM driving route (real road path) */}
        {showRoute && routeCoords && routeCoords.length >= 2 && (
          <>
            {/* Route shadow for depth effect */}
            <Polyline
              positions={routeCoords}
              pathOptions={{
                color: "#1E3A5F",
                weight: 7,
                opacity: 0.25,
                lineCap: "round",
                lineJoin: "round",
              }}
            />
            {/* Main route line */}
            <Polyline
              positions={routeCoords}
              pathOptions={{
                color: "#3B82F6",
                weight: 5,
                opacity: 0.85,
                lineCap: "round",
                lineJoin: "round",
              }}
            />
          </>
        )}

        {/* Fallback straight dashed line when OSRM route not yet loaded */}
        {showRoute &&
          !routeCoords &&
          technicianPosition?.[0] &&
          customerPosition?.[0] && (
            <Polyline
              positions={[technicianPosition, customerPosition]}
              pathOptions={{
                color: "#3B82F6",
                weight: 4,
                opacity: 0.5,
                dashArray: "10, 10",
              }}
            />
          )}

        {/* Technician marker */}
        {technicianPosition?.[0] && technicianPosition?.[1] && (
          <AnimatedMarker position={technicianPosition} icon={technicianIcon}>
            <Popup>
              <div style={{ textAlign: "center" }}>
                <strong>{technicianName}</strong>
                {status === "on_the_way" && (
                  <div
                    style={{
                      fontSize: "0.85rem",
                      color: "#10B981",
                      marginTop: "4px",
                    }}
                  >
                    On the way 🚗
                  </div>
                )}
                {status === "in_progress" && (
                  <div
                    style={{
                      fontSize: "0.85rem",
                      color: "#F59E0B",
                      marginTop: "4px",
                    }}
                  >
                    Working 🔧
                  </div>
                )}
              </div>
            </Popup>
          </AnimatedMarker>
        )}

        {/* Customer/Destination marker */}
        {customerPosition?.[0] && customerPosition?.[1] && (
          <Marker position={customerPosition} icon={customerIcon}>
            <Popup>
              <div style={{ textAlign: "center" }}>
                <strong>Destination</strong>
                <div style={{ fontSize: "0.85rem", marginTop: "4px" }}>
                  {customerAddress}
                </div>
              </div>
            </Popup>
          </Marker>
        )}

        {/* Self marker (for technician view) */}
        {mode === "technician" && selfPosition?.[0] && selfPosition?.[1] && (
          <Marker position={selfPosition} icon={originIcon}>
            <Popup>
              <div style={{ textAlign: "center" }}>
                <strong>Your Location</strong>
              </div>
            </Popup>
          </Marker>
        )}
      </MapContainer>

      {/* Status bar at bottom */}
      <div
        style={{
          marginTop: "-4px",
          background:
            status === "on_the_way"
              ? "#EFF6FF"
              : status === "in_progress"
                ? "#FEF3C7"
                : "#F0FDF4",
          borderRadius: "0 0 12px 12px",
          padding: "12px 16px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ fontSize: "1.2rem" }}>
            {status === "on_the_way"
              ? "🚗"
              : status === "in_progress"
                ? "🔧"
                : "✓"}
          </span>
          <span style={{ fontWeight: "500" }}>
            {status === "on_the_way"
              ? "Technician is on the way"
              : status === "in_progress"
                ? "Service in progress"
                : status === "accepted"
                  ? "Technician will start shortly"
                  : "Live tracking"}
          </span>
        </div>
        <div style={{ fontSize: "0.75rem", color: "#666" }}>
          Live • Updated now
        </div>
      </div>
    </div>
  );
}

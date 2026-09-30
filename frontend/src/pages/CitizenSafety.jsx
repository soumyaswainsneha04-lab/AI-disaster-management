import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Link } from "react-router-dom";
import L from "leaflet";
import { apiFetch } from "../api";
import { useAuth } from "../auth/AuthContext";
import {
  DataContextStrip,
  EmergencyHelpCard,
} from "../components/Common";

const QUICK_CITIES = [
  ["Bhubaneswar, Odisha", 20.2961, 85.8245],
  ["Kolkata, West Bengal", 22.5726, 88.3639],
  ["New Delhi, Delhi", 28.6139, 77.2090],
  ["Mumbai, Maharashtra", 19.076, 72.8777],
  ["Chennai, Tamil Nadu", 13.0827, 80.2707],
  ["Bengaluru, Karnataka", 12.9716, 77.5946],
  ["Hyderabad, Telangana", 17.385, 78.4867],
  ["Patna, Bihar", 25.5941, 85.1376],
  ["Guwahati, Assam", 26.1445, 91.7362],
  ["Kochi, Kerala", 9.9312, 76.2673],
];

const RISK_COPY = {
  CRITICAL: "Critical prototype risk",
  HIGH: "High prototype risk",
  MODERATE: "Moderate prototype risk",
  LOW: "Low prototype risk",
  UNKNOWN: "Risk unavailable",
};

function compactNumber(value) {
  return Number(value || 0).toLocaleString();
}

export default function CitizenSafety({ publicMode = false }) {
  const { user } = useAuth();
  const [latitude, setLatitude] = useState(20.2961);
  const [longitude, setLongitude] = useState(85.8245);
  const [placeLabel, setPlaceLabel] = useState("Bhubaneswar, Odisha");
  const [assessment, setAssessment] = useState(null);
  const [loading, setLoading] = useState(false);
  const [locating, setLocating] = useState(false);
  const [error, setError] = useState("");
  const [savedLocation, setSavedLocation] = useState(null);
  const [assessmentUpdatedAt, setAssessmentUpdatedAt] = useState(null);

  const [cityQuery, setCityQuery] = useState("");
  const [cityResults, setCityResults] = useState([]);
  const [searchingCities, setSearchingCities] = useState(false);

  const mapElement = useRef(null);
  const mapRef = useRef(null);
  const layerGroupRef = useRef(null);
  const boundaryLayerRef = useRef(null);

  const nearest = assessment?.nearest_disaster;
  const depot = assessment?.nearest_relief_center;

  async function assess(lat = latitude, lon = longitude, label = placeLabel) {
    setLoading(true);
    setError("");
    setPlaceLabel(label);

    try {
      const result = await apiFetch(
        `/public/safety-assessment?latitude=${encodeURIComponent(lat)}&longitude=${encodeURIComponent(lon)}`,
        { auth: false }
      );
      setLatitude(Number(lat));
      setLongitude(Number(lon));
      setAssessment(result);
      setAssessmentUpdatedAt(new Date().toISOString());
    } catch (err) {
      setError(err.message || "Unable to assess this location.");
    } finally {
      setLoading(false);
    }
  }

  function useCurrentLocation() {
    setError("");

    // Mobile browsers require geolocation to run in a secure context.
    // localhost is treated specially on a computer, but a phone opening
    // http://192.168.x.x is NOT a secure context.
    if (!window.isSecureContext) {
      setError(
        "Current location requires a secure HTTPS connection on mobile. " +
        "Open the secure mobile URL for Disaster AI India, then allow Location permission. " +
        "You can still search any Indian city manually on this page."
      );
      return;
    }

    if (!navigator.geolocation) {
      setError(
        "Location access is not supported by this browser. Search for your city instead."
      );
      return;
    }

    setLocating(true);

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLocating(false);

        assess(
          position.coords.latitude,
          position.coords.longitude,
          "My current location"
        );
      },

      (geoError) => {
        setLocating(false);

        if (geoError?.code === 1) {
          setError(
            "Location permission is blocked. Open your browser/site permissions, allow Location for Disaster AI India, then try again."
          );
          return;
        }

        if (geoError?.code === 2) {
          setError(
            "Your phone could not determine its current location. Turn on Location/GPS and try again, or search your city manually."
          );
          return;
        }

        if (geoError?.code === 3) {
          setError(
            "Location lookup timed out. Make sure Location/GPS is enabled and try again."
          );
          return;
        }

        setError(
          "Current location could not be retrieved. Search your city manually or try again."
        );
      },

      {
        enableHighAccuracy: true,
        timeout: 20000,
        maximumAge: 0,
      }
    );
  }

  async function searchAnyCity(event) {
    event?.preventDefault();
    const query = cityQuery.trim();

    if (query.length < 2) {
      setError("Type at least 2 characters of a city, town or locality in India.");
      return;
    }

    setSearchingCities(true);
    setError("");
    setCityResults([]);

    try {
      const data = await apiFetch(
        `/public/geocode?q=${encodeURIComponent(query)}&limit=8`,
        { auth: false }
      );
      setCityResults(data.results || []);

      if (!(data.results || []).length) {
        setError("No matching Indian place was found. Try a nearby town, district or a more specific name.");
      }
    } catch (err) {
      setError(err.message || "Unable to search Indian cities right now.");
    } finally {
      setSearchingCities(false);
    }
  }

  function chooseQuickCity(event) {
    const index = Number(event.target.value);
    if (!Number.isInteger(index) || index < 0) return;

    const [label, lat, lon] = QUICK_CITIES[index];
    setCityResults([]);
    setCityQuery(label);
    assess(lat, lon, label);
  }

  function chooseSearchResult(result) {
    setCityResults([]);
    setCityQuery(result.label);
    assess(result.latitude, result.longitude, result.label);
  }

  useEffect(() => {
    if (publicMode || !user) return;

    apiFetch("/profile/preferences")
      .then((data) => {
        const preferences = data.preferences || {};

        if (
          preferences.home_latitude != null &&
          preferences.home_longitude != null
        ) {
          setSavedLocation(preferences);
        }
      })
      .catch(() => {
        // Saved location is optional. My Safety continues without it.
      });
  }, [publicMode, user]);

  function useSavedLocation() {
    if (!savedLocation) return;

    assess(
      savedLocation.home_latitude,
      savedLocation.home_longitude,
      savedLocation.home_label || "My saved location"
    );
  }

  useEffect(() => {
    assess(latitude, longitude, placeLabel);
    // Initial prototype location only; the user can replace it immediately.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!assessment || loading || !mapElement.current || mapRef.current) {
      return;
    }

    const map = L.map(mapElement.current, {
      minZoom: 4,
      maxZoom: 14,
      maxBounds: [
        [6, 68],
        [38, 98],
      ],
      maxBoundsViscosity: 1,
    }).setView([latitude, longitude], 7);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);

    layerGroupRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;

    let cancelled = false;
    apiFetch("/public/india-boundary", { auth: false })
      .then((boundary) => {
        if (cancelled || !mapRef.current) return;
        boundaryLayerRef.current = L.geoJSON(boundary, {
          style: {
            color: "#1f4f7a",
            weight: 2,
            fillOpacity: 0.02,
          },
        }).addTo(mapRef.current);
      })
      .catch(() => {});

    const resizeTimer = setTimeout(() => {
      map.invalidateSize(true);
    }, 150);

    return () => {
      cancelled = true;
      clearTimeout(resizeTimer);
      map.remove();
      mapRef.current = null;
      layerGroupRef.current = null;
      boundaryLayerRef.current = null;
    };
  }, [assessment, loading, latitude, longitude]);

  useEffect(() => {
    const map = mapRef.current;
    const group = layerGroupRef.current;
    if (!map || !group || !assessment) return;

    group.clearLayers();
    const bounds = [];

    const userMarker = L.circleMarker([latitude, longitude], {
      radius: 9,
      color: "#1d4ed8",
      fillColor: "#3b82f6",
      fillOpacity: 0.95,
      weight: 3,
    }).bindPopup(`<strong>Your selected location</strong><br/>${placeLabel}`);
    group.addLayer(userMarker);
    bounds.push([latitude, longitude]);

    (assessment.nearby_disasters || []).slice(0, 6).forEach((event) => {
      const eventLat = Number(event.latitude);
      const eventLon = Number(event.longitude);
      if (!Number.isFinite(eventLat) || !Number.isFinite(eventLon)) return;

      const marker = L.circleMarker([eventLat, eventLon], {
        radius: 7,
        color: "#b42318",
        fillColor: "#ef4444",
        fillOpacity: 0.8,
      }).bindPopup(
        `<strong>${event.disaster_type}</strong><br/>${event.disaster_subtype || "Disaster event"}<br/>${event.distance_km} km from selected location`
      );
      group.addLayer(marker);
      bounds.push([eventLat, eventLon]);
    });

    (assessment.nearby_relief_centers || []).forEach((center) => {
      const marker = L.circleMarker([center.latitude, center.longitude], {
        radius: 7,
        color: "#047857",
        fillColor: "#10b981",
        fillOpacity: 0.9,
      }).bindPopup(
        `<strong>${center.name}</strong><br/>${center.city}, ${center.state}<br/>Prototype relief resource center · ${center.distance_km} km`
      );
      group.addLayer(marker);
      bounds.push([center.latitude, center.longitude]);
    });

    if (bounds.length > 1) {
      map.fitBounds(L.latLngBounds(bounds), {
        padding: [35, 35],
        maxZoom: 8,
      });
    } else {
      map.setView([latitude, longitude], 7);
    }

    setTimeout(() => map.invalidateSize(true), 80);
  }, [assessment, latitude, longitude, placeLabel]);

  const reliefCards = useMemo(() => {
    const resources = depot?.resources || {};
    return [
      ["Food", resources.food_packets, "packets"],
      ["Water", resources.water_litres, "L"],
      ["Medical", resources.medical_kits, "kits"],
      ["Shelter", resources.shelter_capacity, "people"],
    ];
  }, [depot]);

  return (
    <div className={publicMode ? "citizen-public-shell" : ""}>
      {publicMode && (
        <header className="citizen-public-topbar">
          <div className="citizen-public-brand">
            <div
            className="brand-mark"
            data-no-translate
            >
              IN
              </div>
            <div>
              <strong data-no-translate>
                Disaster AI India
                </strong>
              <span>Citizen Safety</span>
            </div>
          </div>
          <div className="citizen-public-actions">
            <Link to="/login" className="small-button">Sign in</Link>
            <Link to="/signup" className="primary-button">Create Account</Link>
          </div>
        </header>
      )}

      <div className={publicMode ? "citizen-public-content" : ""}>
        <EmergencyHelpCard compact />

        <DataContextStrip
          mode="AI ESTIMATE"
          source="Project disaster dataset + location-based decision support"
          updatedAt={assessmentUpdatedAt}
          status="Prototype guidance"
        />

        <div className="citizen-safety-hero">
          <div>
            <span className="eyebrow">INDIA CITIZEN SAFETY</span>
            <h1>
              {publicMode
                ? "What is happening near you?"
                : `Stay informed${user?.name ? `, ${user.name.split(" ")[0]}` : ""}.`}
            </h1>
            <p>
              Use your live location or search any city, town or locality in
              India. The system then checks nearby prototype disaster records
              and relief resources.
            </p>
          </div>
          {!publicMode && <div className="citizen-role-pill">Citizen View</div>}
        </div>

        <section className="citizen-location-card citizen-location-card-expanded">
          <div className="citizen-location-copy">
            <strong>Where are you?</strong>
            <span>
              You are no longer limited to a small preset list. Search for any
              Indian city, town, village or locality.
            </span>
          </div>

          <div className="citizen-location-controls location-search-controls">
            <button
              type="button"
              className="primary-button location-button"
              onClick={useCurrentLocation}
              disabled={locating || loading}
            >
              {locating ? "Finding location..." : "⌖ Use My Current Location"}
            </button>

            {!publicMode && savedLocation && (
              <button
                type="button"
                className="small-button saved-location-button"
                onClick={useSavedLocation}
                disabled={loading}
              >
                ★ Use Saved Location
              </button>
            )}

            <span className="location-or">or</span>

            <form className="india-city-search" onSubmit={searchAnyCity}>
              <input
                value={cityQuery}
                onChange={(event) => setCityQuery(event.target.value)}
                placeholder="Search any city, town or locality in India"
              />
              <button className="small-button" disabled={searchingCities}>
                {searchingCities ? "Searching..." : "Search"}
              </button>
            </form>

            <select defaultValue="" onChange={chooseQuickCity} disabled={loading}>
              <option value="" disabled>Quick city shortcuts</option>
              {QUICK_CITIES.map(([label], index) => (
                <option key={label} value={index}>{label}</option>
              ))}
            </select>
          </div>

          {!window.isSecureContext && (
            <div className="mobile-location-security-note">
              <strong>Phone GPS needs HTTPS</strong>
              <span>
                This page is currently opened over an insecure local HTTP address.
                City search still works, but "Use My Current Location" will work
                after opening the secure HTTPS mobile URL.
              </span>
            </div>
          )}

          {cityResults.length > 0 && (
            <div className="india-city-results">
              {cityResults.map((result, index) => (
                <button
                  type="button"
                  key={`${result.latitude}-${result.longitude}-${index}`}
                  onClick={() => chooseSearchResult(result)}
                >
                  <strong>{result.city}</strong>
                  <span>{result.state}</span>
                  <small>{result.label}</small>
                </button>
              ))}
            </div>
          )}
        </section>

        {error && <div className="state-box error-box">{error}</div>}
        {loading && <div className="state-box">Checking nearby disaster information...</div>}

        {assessment && !loading && (
          <>
            <div className="citizen-status-grid">
              <article className={`citizen-risk-card risk-${String(assessment.risk_level || "unknown").toLowerCase()}`}>
                <span>Current prototype risk</span>
                <strong>{RISK_COPY[assessment.risk_level] || assessment.risk_level}</strong>
                <small>{placeLabel}</small>
              </article>

              <article className="citizen-summary-card">
                <span>Nearest recorded disaster</span>
                <strong>{nearest ? nearest.disaster_type : "None found"}</strong>
                <small>{nearest ? `${nearest.distance_km} km away` : "No nearby dataset record"}</small>
              </article>

              <article className="citizen-summary-card">
                <span>Nearest relief resource center</span>
                <strong>{depot ? depot.city : "Unavailable"}</strong>
                <small>{depot ? `${depot.distance_km} km · ${depot.state}` : "No depot available"}</small>
              </article>
            </div>

            <section className="citizen-decision-card">
              <div className="citizen-decision-main">
                <span className="eyebrow">WHAT SHOULD I DO?</span>
                <h2>{assessment.decision_summary}</h2>
                <ul>
                  {(assessment.safety_actions || []).map((action) => (
                    <li key={action}>{action}</li>
                  ))}
                </ul>
              </div>

              {nearest && (
                <div className="citizen-event-facts">
                  <div><span>Event</span><strong>{nearest.disaster_subtype || nearest.disaster_type}</strong></div>
                  <div><span>Severity</span><strong>{Math.round(Number(nearest.severity_score || 0) * 100)}%</strong></div>
                  <div><span>Affected population</span><strong>{compactNumber(nearest.affected_population)}</strong></div>
                  <div><span>Road blockage</span><strong>{Math.round(Number(nearest.road_blockage_probability || 0) * 100)}%</strong></div>
                </div>
              )}
            </section>

            <div className="citizen-two-column">
              <section className="panel citizen-map-panel">
                <div className="panel-heading">
                  <div>
                    <h3>Nearby Situation Map</h3>
                    <p>Blue = your location · Red = India disaster records · Green = prototype relief depots</p>
                  </div>
                </div>
                <div
                  ref={mapElement}
                  className="citizen-safety-map"
                  style={{ width: "100%", height: "430px", minHeight: "430px" }}
                />
              </section>

              <section className="panel relief-center-panel">
                <div className="panel-heading">
                  <div>
                    <h3>Nearby Relief Resources</h3>
                    <p>{depot ? `${depot.name} · ${depot.city}, ${depot.state}` : "Resource center unavailable"}</p>
                  </div>
                </div>

                {depot && (
                  <>
                    <div className="relief-distance-line">
                      <span>Distance from you</span>
                      <strong>{depot.distance_km} km</strong>
                    </div>
                    <div className="citizen-relief-grid">
                      {reliefCards.map(([label, value, unit]) => (
                        <div key={label}>
                          <span>{label}</span>
                          <strong>{compactNumber(value)}</strong>
                          <small>{unit}</small>
                        </div>
                      ))}
                    </div>
                  </>
                )}

                <div className="citizen-prototype-note">
                  These depot locations are project-defined prototype resource centers, not official public shelters.
                </div>
              </section>
            </div>

            <section className="panel nearby-list-panel">
              <div className="panel-heading">
                <div>
                  <h3>Nearby Disaster Records</h3>
                  <p>Closest records that pass the India boundary filter</p>
                </div>
              </div>

              <div className="nearby-disaster-list">
                {(assessment.nearby_disasters || []).slice(0, 5).map((event) => (
                  <div key={event.row_id} className="nearby-disaster-row">
                    <div>
                      <span className="disaster-chip">{event.disaster_type}</span>
                      <strong>{event.disaster_subtype || `Incident #${event.row_id}`}</strong>
                    </div>
                    <div><span>Distance</span><strong>{event.distance_km} km</strong></div>
                    <div><span>Severity</span><strong>{Math.round(Number(event.severity_score || 0) * 100)}%</strong></div>
                    <div><span>Affected</span><strong>{compactNumber(event.affected_population)}</strong></div>
                  </div>
                ))}
              </div>
            </section>

            <div className="citizen-official-warning">
              <strong>Important</strong>
              <span>{assessment.disclaimer}</span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

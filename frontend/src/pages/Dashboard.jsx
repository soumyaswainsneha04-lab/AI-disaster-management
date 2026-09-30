import { useEffect, useState } from "react";
import { apiFetch } from "../api";
import { useAuth } from "../auth/AuthContext";
import {
  PageHeader,
  MetricCard,
  StatusBadge,
  ErrorBlock,
  LoadingBlock,
  LeafletMap,
  DataContextStrip,
  EmergencyHelpCard,
} from "../components/Common";

const STAFF_ROLES = ["ADMIN", "RELIEF_COORDINATOR", "FIELD_TEAM"];

export default function Dashboard() {
  const { user } = useAuth();

  const [health, setHealth] = useState(null);
  const [dataset, setDataset] = useState(null);
  const [zones, setZones] = useState([]);
  const [depots, setDepots] = useState([]);
  const [missions, setMissions] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);

  const canViewMissions = STAFF_ROLES.includes(user?.role);

  useEffect(() => {
    async function loadDashboard() {
      setLoading(true);
      setError("");

      try {
        const requests = [
          apiFetch("/health"),
          apiFetch("/dataset-info"),
          apiFetch("/operations/zones?limit=250"),
          apiFetch("/inventory"),
        ];

        if (canViewMissions) {
          requests.push(apiFetch("/missions"));
        }

        const results = await Promise.all(requests);

        setHealth(results[0]);
        setDataset(results[1]);
        setZones(results[2]?.zones || []);
        setDepots(results[3]?.depots || []);
        setMissions(canViewMissions ? results[4] : null);
        setLastUpdated(new Date().toISOString());
      } catch (err) {
        setError(err.message || "Unable to load dashboard.");
      } finally {
        setLoading(false);
      }
    }

    if (user) {
      loadDashboard();
    }
  }, [user, canViewMissions]);

  if (loading || !health || !dataset) {
    return (
      <>
        <PageHeader
          title="India Emergency Response Dashboard"
          subtitle="Disaster AI India"
        />
        <ErrorBlock error={error} />
        {!error && (
          <LoadingBlock text="Connecting to India response platform..." />
        )}
      </>
    );
  }

  const activeMissions = canViewMissions
    ? (missions?.missions || []).filter(
        (mission) => !["COMPLETED", "CANCELLED"].includes(mission.status)
      ).length
    : null;

  return (
    <div>
      <PageHeader
        title="India Emergency Response Dashboard"
        subtitle="India-focused command center for disaster impact, resource planning, logistics and response support."
      />

      <DataContextStrip
        mode="PROJECT DATA"
        source="India project dataset + prototype depot network"
        updatedAt={lastUpdated}
        status={health.status}
      />

      <EmergencyHelpCard compact />

      <div className="hero-strip india-hero">
        <div>
          <span className="eyebrow">INDIA OPERATING REGION</span>
          <h2>Emergency Intelligence Platform</h2>
          <p>Flood · Cyclone · Earthquake · Wildfire · Landslide</p>
        </div>
        <StatusBadge value={health.status} />
      </div>

      <div className="metrics-grid">
        <MetricCard
          label="India-Mapped Records"
          value={Number(health.india_mapped_records || dataset.total_records || 0).toLocaleString()}
          hint={`Source dataset: ${Number(health.dataset_records || 0).toLocaleString()} rows`}
        />
        <MetricCard
          label="Supported Disasters"
          value={health.supported_disasters?.length || 0}
        />
        <MetricCard label="Prototype Relief Depots" value={depots.length} />
        {canViewMissions && (
          <MetricCard label="Active Missions" value={activeMissions} />
        )}
      </div>

      <div className="dashboard-grid">
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h3>Disaster Distribution</h3>
              <p>Indian operating dataset by disaster type</p>
            </div>
          </div>

          <div className="count-list">
            {Object.entries(dataset.disaster_counts || {}).map(
              ([name, count]) => {
                const percentage = dataset.total_records
                  ? (Number(count) / Number(dataset.total_records)) * 100
                  : 0;

                return (
                  <div className="count-row" key={name}>
                    <div className="count-row-top">
                      <span>{name}</span>
                      <strong>{Number(count).toLocaleString()}</strong>
                    </div>
                    <div className="progress-track">
                      <div
                        className="progress-bar"
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </div>
                );
              }
            )}
          </div>
        </section>

        <section className="panel map-panel">
          <div className="panel-heading">
            <div>
              <h3>India Disaster & Resource Map</h3>
              <p>
                Representative disaster zones inside India plus prototype
                resource-depot locations
              </p>
            </div>
            <div className="map-legend compact-map-legend">
              <span>● Disaster zones</span>
              <span className="depot-legend">● Resource depots</span>
            </div>
          </div>

          <LeafletMap points={zones} depots={depots} />
        </section>
      </div>

      <div className="prototype-note">
        Disaster markers are filtered by the India boundary mask and spatially
        sampled instead of taking the first rows. The loaded project dataset
        itself is geographically concentrated in eastern/northeastern India,
        so the dashboard does not invent disaster zones in regions where the
        dataset has no coordinates. Resource depots are project-defined
        demonstration locations.
      </div>
    </div>
  );
}

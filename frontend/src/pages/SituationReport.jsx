import { useMemo, useState } from "react";
import { apiFetch } from "../api";
import {
  PageHeader,
  RecordPicker,
  ErrorBlock,
  LoadingBlock,
  StatusBadge,
} from "../components/Common";

const RESOURCE_ROWS = [
  ["Food", "food_packets"],
  ["Water", "water_litres"],
  ["Medical Kits", "medical_kits"],
  ["Shelter", "shelter_people"],
];

function number(value) {
  return Number(value || 0).toLocaleString();
}

function percent(value) {
  return `${Math.round(Number(value || 0) * 100)}%`;
}

function MiniStat({ label, value, hint }) {
  return (
    <div className="sitrep-mini-stat">
      <span>{label}</span>
      <strong>{value ?? "—"}</strong>
      {hint && <small>{hint}</small>}
    </div>
  );
}

function Empty({ children = "No information recorded." }) {
  return <div className="sitrep-empty">{children}</div>;
}

export default function SituationReport() {
  const [rowId, setRowId] = useState(null);
  const [data, setData] = useState(null);
  const [activeTab, setActiveTab] = useState("overview");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function run() {
    setLoading(true);
    setError("");
    setActiveTab("overview");

    try {
      setData(await apiFetch(`/reports/situation/${rowId}`));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function download() {
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `situation_report_${rowId}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  const prediction = data?.resource_prediction?.predicted_resources || {};
  const allocation = data?.resource_allocation || {};
  const allocated = allocation.allocated_resources || {};
  const shortage = allocation.shortage || {};
  const evacuation = data?.evacuation_plan || {};
  const transport = data?.transport_recommendation || {};
  const logistics = data?.logistics_bottlenecks || {};
  const stock = data?.stock_monitoring || {};
  const teams = data?.team_deployment || {};

  const activityCounts = useMemo(
    () => ({
      missions: data?.missions?.length || 0,
      reports: data?.field_reports?.length || 0,
    }),
    [data]
  );

  return (
    <div className="situation-page sitrep-page">
      <PageHeader
        title="Situation Report"
        subtitle="A compact incident briefing. Use the tabs instead of scrolling through the full raw JSON structure."
      />

      <div className="sitrep-top-controls">
        <RecordPicker rowId={rowId} setRowId={setRowId} />

        <div className="report-actions sitrep-actions">
          <button className="primary-button" onClick={run} disabled={loading || rowId === null || rowId === undefined}>
            {loading ? "Generating..." : "Generate Situation Report"}
          </button>
          {data && (
            <>
              <button className="small-button" onClick={download}>Download JSON</button>
              <button className="small-button" onClick={() => window.print()}>Print / Save PDF</button>
            </>
          )}
        </div>
      </div>

      <ErrorBlock error={error} />
      {loading && <LoadingBlock text="Building situation report..." />}

      {data && (
        <>
          <section className="sitrep-cover-card">
            <div>
              <span className="eyebrow">SITREP · INDIA</span>
              <h2>
                {data.incident.disaster_type}
                {data.incident.disaster_subtype ? ` · ${data.incident.disaster_subtype}` : ""}
              </h2>
              <p>
                Zone #{data.incident.row_id} · Generated {new Date(data.generated_at).toLocaleString()}
              </p>
            </div>
            <StatusBadge value={data.incident.impact_class} />
          </section>

          <div className="sitrep-kpi-grid">
            <MiniStat label="Affected Population" value={number(data.incident.affected_population)} />
            <MiniStat label="Severity" value={percent(data.incident.severity_score)} />
            <MiniStat label="DRIS Score" value={data.incident.dris_score} />
            <MiniStat label="Priority" value={allocation.priority_level || "—"} hint={allocation.priority_score != null ? `Score ${allocation.priority_score}` : ""} />
          </div>

          <nav className="sitrep-tabs" aria-label="Situation report sections">
            {[
              ["overview", "Overview"],
              ["resources", "Resources"],
              ["operations", "Operations"],
              ["activity", `Activity (${activityCounts.missions + activityCounts.reports})`],
            ].map(([key, label]) => (
              <button
                key={key}
                className={activeTab === key ? "active" : ""}
                onClick={() => setActiveTab(key)}
              >
                {label}
              </button>
            ))}
          </nav>

          {activeTab === "overview" && (
            <div className="sitrep-tab-panel">
              <div className="sitrep-card-grid">
                <section className="sitrep-section-card">
                  <div className="sitrep-card-title">
                    <div>
                      <span>EVACUATION</span>
                      <h3>Evacuation Decision</h3>
                    </div>
                    <StatusBadge value={evacuation.evacuation_urgency || "UNKNOWN"} />
                  </div>
                  <div className="sitrep-detail-grid">
                    <MiniStat label="Shelter Required" value={number(evacuation.people_requiring_shelter)} />
                    <MiniStat label="Existing Capacity" value={number(evacuation.existing_shelter_capacity)} />
                    <MiniStat label="Shelter Deficit" value={number(evacuation.shelter_deficit)} />
                    <MiniStat label="Additional Camps" value={number(evacuation.additional_camps_required)} />
                  </div>
                </section>

                <section className="sitrep-section-card">
                  <div className="sitrep-card-title">
                    <div>
                      <span>TRANSPORT</span>
                      <h3>Recommended Response Mode</h3>
                    </div>
                  </div>
                  <div className="sitrep-callout">
                    {transport.recommended_primary_mode || "No recommendation available"}
                  </div>
                  <div className="sitrep-tag-row">
                    {(transport.alternative_modes || []).map((mode) => (
                      <span key={mode}>{mode}</span>
                    ))}
                  </div>
                </section>

                <section className="sitrep-section-card sitrep-wide-card">
                  <div className="sitrep-card-title">
                    <div>
                      <span>LOGISTICS</span>
                      <h3>Operational Bottlenecks</h3>
                    </div>
                    <StatusBadge value={logistics.overall_logistics_risk || "UNKNOWN"} />
                  </div>
                  <p className="sitrep-recommendation">
                    {logistics.recommendation || "No logistics recommendation available."}
                  </p>
                  {(logistics.detected_bottlenecks || []).length ? (
                    <div className="sitrep-bottleneck-grid">
                      {logistics.detected_bottlenecks.slice(0, 6).map((item, index) => (
                        <div key={`${item.factor}-${index}`}>
                          <span>{item.factor}</span>
                          <strong>{item.value}</strong>
                          <StatusBadge value={item.risk} />
                        </div>
                      ))}
                    </div>
                  ) : (
                    <Empty>No significant bottlenecks detected in the prototype inputs.</Empty>
                  )}
                </section>
              </div>
            </div>
          )}

          {activeTab === "resources" && (
            <div className="sitrep-tab-panel">
              <section className="sitrep-section-card">
                <div className="sitrep-card-title">
                  <div>
                    <span>RESOURCE PLAN</span>
                    <h3>Demand, Allocation and Shortage</h3>
                  </div>
                </div>

                <div className="sitrep-resource-table-wrap">
                  <table className="sitrep-resource-table">
                    <thead>
                      <tr>
                        <th>Resource</th>
                        <th>Predicted Need</th>
                        <th>Allocated</th>
                        <th>Shortage</th>
                      </tr>
                    </thead>
                    <tbody>
                      {RESOURCE_ROWS.map(([label, key]) => (
                        <tr key={key}>
                          <td>{label}</td>
                          <td>{number(prediction[key])}</td>
                          <td>{number(allocated[key])}</td>
                          <td className={Number(shortage[key] || 0) > 0 ? "danger-text" : "success-text"}>
                            {number(shortage[key])}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              <div className="sitrep-card-grid sitrep-resource-bottom">
                <section className="sitrep-section-card">
                  <div className="sitrep-card-title">
                    <div>
                      <span>SOURCE</span>
                      <h3>Primary Relief Depot</h3>
                    </div>
                  </div>
                  {allocation.primary_source_depot ? (
                    <div className="sitrep-depot-box">
                      <strong>{allocation.primary_source_depot.name}</strong>
                      <span>
                        {allocation.primary_source_depot.city}, {allocation.primary_source_depot.state}
                      </span>
                      <small>{allocation.primary_source_depot.distance_km} km from disaster zone</small>
                    </div>
                  ) : (
                    <Empty />
                  )}
                </section>

                <section className="sitrep-section-card">
                  <div className="sitrep-card-title">
                    <div>
                      <span>STOCK</span>
                      <h3>Stock Depletion</h3>
                    </div>
                  </div>
                  <div className="sitrep-callout">
                    {stock.first_resource_expected_to_deplete
                      ? `${stock.first_resource_expected_to_deplete.replaceAll("_", " ")} may deplete first`
                      : "No immediate depletion identified"}
                  </div>
                  {stock.estimated_first_depletion_hours != null && (
                    <small className="sitrep-muted-line">
                      Estimated in {stock.estimated_first_depletion_hours} hours
                    </small>
                  )}
                </section>
              </div>
            </div>
          )}

          {activeTab === "operations" && (
            <div className="sitrep-tab-panel">
              <div className="sitrep-card-grid">
                <section className="sitrep-section-card">
                  <div className="sitrep-card-title">
                    <div>
                      <span>TEAM DEPLOYMENT</span>
                      <h3>Response Staffing</h3>
                    </div>
                  </div>
                  <div className="sitrep-detail-grid">
                    {Object.entries(teams)
                      .filter(([key, value]) =>
                        typeof value !== "object" &&
                        !["feature", "row_id", "disaster_type", "note"].includes(key)
                      )
                      .slice(0, 8)
                      .map(([key, value]) => (
                        <MiniStat key={key} label={key.replaceAll("_", " ")} value={String(value)} />
                      ))}
                  </div>
                </section>

                <section className="sitrep-section-card">
                  <div className="sitrep-card-title">
                    <div>
                      <span>ACCESS</span>
                      <h3>Logistics Distances</h3>
                    </div>
                  </div>
                  <div className="sitrep-detail-grid">
                    <MiniStat label="Depot" value={`${logistics.nearest_depot_distance_km ?? "—"} km`} />
                    <MiniStat label="Hospital" value={`${logistics.nearest_hospital_distance_km ?? "—"} km`} />
                    <MiniStat label="Evacuation Center" value={`${logistics.nearest_evacuation_center_km ?? "—"} km`} />
                    <MiniStat label="Logistics Risk Score" value={logistics.logistics_risk_score ?? "—"} />
                  </div>
                </section>
              </div>
            </div>
          )}

          {activeTab === "activity" && (
            <div className="sitrep-tab-panel">
              <div className="sitrep-card-grid">
                <section className="sitrep-section-card">
                  <div className="sitrep-card-title">
                    <div>
                      <span>MISSIONS</span>
                      <h3>Recent Mission Activity</h3>
                    </div>
                    <strong className="sitrep-count-badge">{activityCounts.missions}</strong>
                  </div>
                  {(data.missions || []).length ? (
                    <div className="sitrep-activity-list">
                      {data.missions.slice(-5).reverse().map((mission, index) => (
                        <div key={mission.mission_id || index}>
                          <strong>{mission.mission_type || mission.title || "Mission"}</strong>
                          <span>{mission.status || "Recorded"}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <Empty>No missions recorded for this incident.</Empty>
                  )}
                </section>

                <section className="sitrep-section-card">
                  <div className="sitrep-card-title">
                    <div>
                      <span>FIELD REPORTS</span>
                      <h3>Recent Field Reports</h3>
                    </div>
                    <strong className="sitrep-count-badge">{activityCounts.reports}</strong>
                  </div>
                  {(data.field_reports || []).length ? (
                    <div className="sitrep-activity-list">
                      {data.field_reports.slice(-5).reverse().map((report, index) => (
                        <div key={report.report_id || index}>
                          <strong>{report.road_status || "Field update"}</strong>
                          <span>{report.notes || `Severity ${report.reported_severity ?? "—"}`}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <Empty>No field reports recorded for this incident.</Empty>
                  )}
                </section>

                <section className="sitrep-section-card sitrep-wide-card">
                  <div className="sitrep-card-title">
                    <div>
                      <span>LIMITATIONS</span>
                      <h3>Prototype Notes</h3>
                    </div>
                  </div>
                  <div className="sitrep-limitations">
                    {(data.limitations || []).map((item) => (
                      <span key={item}>• {item}</span>
                    ))}
                  </div>
                </section>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

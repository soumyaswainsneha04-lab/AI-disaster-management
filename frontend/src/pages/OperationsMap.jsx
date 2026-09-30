import { useEffect, useState } from "react";
import { apiFetch } from "../api";
import {
  PageHeader,
  ErrorBlock,
  LoadingBlock,
  LeafletMap,
  DataContextStrip,
} from "../components/Common";

export default function OperationsMap() {
  const [types, setTypes] = useState([]);
  const [type, setType] = useState("");
  const [data, setData] = useState(null);
  const [depots, setDepots] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([apiFetch("/disasters/types"), apiFetch("/inventory")])
      .then(([typeData, inventoryData]) => {
        setTypes(typeData.supported_disasters || []);
        setDepots(inventoryData.depots || []);
      })
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    setLoading(true);
    setError("");

    const path = type
      ? `/operations/zones?disaster_type=${encodeURIComponent(type)}&limit=300`
      : "/operations/zones?limit=300";

    apiFetch(path)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [type]);

  return (
    <div>
      <PageHeader
        title="India Operations Map"
        subtitle="Disaster impact zones filtered to Indian territory, together with prototype resource depots."
      />

      <DataContextStrip
        mode="PROJECT DATA"
        source="India-filtered historical disaster coordinates + prototype depots"
        status="Boundary filtered"
      />

      <div className="toolbar compact-toolbar">
        <label>
          Disaster type
          <select value={type} onChange={(event) => setType(event.target.value)}>
            <option value="">All types</option>
            {types.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
        </label>

        <div className="map-legend">
          <span>● Disaster zones</span>
          <span className="depot-legend">● Resource depots</span>
        </div>
      </div>

      <ErrorBlock error={error} />
      {loading && <LoadingBlock text="Loading India impact zones..." />}

      <section className="panel">
        <div className="map-summary-strip">
          <span>
            <strong>{data?.returned_zones || 0}</strong> representative zones
          </span>
          <span>India boundary filter enabled</span>
          {type && <span>{type}</span>}
        </div>

        <LeafletMap points={data?.zones || []} depots={depots} />
      </section>

      <div className="note-box">
        Only disaster coordinates that pass the India boundary mask are shown.
        The loaded project dataset is concentrated in eastern/northeastern
        India, so the map shows valid zones from that coverage area rather than
        plotting points in neighbouring countries or fabricating new zones.
      </div>
    </div>
  );
}

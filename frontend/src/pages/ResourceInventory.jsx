import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

import { apiFetch } from "../api";
import { useAuth } from "../auth/AuthContext";
import {
  PageHeader,
  StatusBadge,
  ErrorBlock,
  LoadingBlock,
  MetricCard,
  INDIA_BOUNDS,
} from "../components/Common";

const labels = {
  food_packets: "Food Packets",
  water_litres: "Water Litres",
  medical_kits: "Medical Kits",
  shelter_capacity: "Shelter Capacity",
  rescue_vehicles: "Rescue Vehicles",
  personnel: "Personnel",
};

const INVENTORY_EDIT_ROLES = [
  "ADMIN",
];

function DepotMap({
  depots,
  selectedId,
  onSelect,
}) {
  const ref = useRef(null);
  const mapRef = useRef(null);

  useEffect(() => {
    if (!ref.current || mapRef.current) {
      return;
    }

    const map = L.map(ref.current, {
      maxBounds: INDIA_BOUNDS,
      maxBoundsViscosity: 1,
      minZoom: 4,
    }).setView([22.6, 79.5], 5);

    L.tileLayer(
      "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
      {
        maxZoom: 18,
        attribution: "&copy; OpenStreetMap contributors",
      }
    ).addTo(map);

    mapRef.current = map;

    setTimeout(() => {
      map.invalidateSize();
    }, 100);

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;

    if (!map) {
      return;
    }

    map.eachLayer((layer) => {
      if (layer instanceof L.CircleMarker) {
        map.removeLayer(layer);
      }
    });

    depots.forEach((depot) => {
      const selected =
        depot.depot_id === selectedId;

      const marker = L.circleMarker(
        [
          depot.latitude,
          depot.longitude,
        ],
        {
          radius: selected ? 10 : 7,
          color: selected
            ? "#7c3aed"
            : "#0f766e",
          weight: selected ? 3 : 2,
          fillColor: "#14b8a6",
          fillOpacity: 0.9,
        }
      );

      marker
        .addTo(map)
        .bindPopup(
          `
          <strong>${depot.name}</strong>
          <br/>
          ${depot.district || depot.city} District
          <br/>
          ${depot.city}, ${depot.state}, India
          <br/>
          ${Number(depot.latitude).toFixed(4)},
          ${Number(depot.longitude).toFixed(4)}
          <br/>
          ${depot.status}
          `
        );

      marker.on("click", () => {
        onSelect(depot.depot_id);
      });
    });

    setTimeout(() => {
      map.invalidateSize();
    }, 50);
  }, [depots, selectedId, onSelect]);

  return (
    <div
      ref={ref}
      className="inventory-map"
    />
  );
}

export default function ResourceInventory() {
  const { user } = useAuth();

  const canUpdateInventory =
    INVENTORY_EDIT_ROLES.includes(
      user?.role
    );

  const [data, setData] =
    useState(null);

  const [selectedId, setSelectedId] =
    useState("");

  const [selectedState, setSelectedState] =
    useState("ALL");

  const [error, setError] =
    useState("");

  const [loading, setLoading] =
    useState(true);

  const [editing, setEditing] =
    useState(null);

  const [qty, setQty] =
    useState("");

  const [reason, setReason] =
    useState("Inventory update");

  const [saving, setSaving] =
    useState(false);

  async function load() {
    setLoading(true);

    try {
      const result =
        await apiFetch("/inventory");

      setData(result);

      if (
        !selectedId &&
        result.depots?.length
      ) {
        setSelectedId(
          result.depots[0].depot_id
        );
      }

      setError("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const depots =
    data?.depots || [];

  const states =
    useMemo(
      () =>
        [
          ...new Set(
            depots.map(
              (depot) => depot.state
            )
          ),
        ].sort(),
      [depots]
    );

  const visibleDepots =
    useMemo(
      () =>
        selectedState === "ALL"
          ? depots
          : depots.filter(
              (depot) =>
                depot.state ===
                selectedState
            ),
      [
        depots,
        selectedState,
      ]
    );

  const selected =
    useMemo(
      () =>
        depots.find(
          (depot) =>
            depot.depot_id ===
            selectedId
        ) ||
        visibleDepots[0] ||
        depots[0],
      [
        depots,
        visibleDepots,
        selectedId,
      ]
    );

  useEffect(() => {
    if (!visibleDepots.length) {
      return;
    }

    const selectedStillVisible =
      visibleDepots.some(
        (depot) =>
          depot.depot_id ===
          selectedId
      );

    if (!selectedStillVisible) {
      setSelectedId(
        visibleDepots[0].depot_id
      );
    }
  }, [
    visibleDepots,
    selectedId,
  ]);

  async function save(resource) {
    if (!canUpdateInventory) {
      setError(
        "You have read-only inventory access."
      );
      return;
    }

    setSaving(true);
    setError("");

    try {
      await apiFetch(
        `/inventory/depots/${selected.depot_id}/${resource}`,
        {
          method: "PUT",
          body: JSON.stringify({
            quantity: Number(qty),
            reason,
          }),
        }
      );

      setEditing(null);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="India Resource Inventory"
        subtitle={
          canUpdateInventory
            ? "View relief inventory locations and update depot stock."
            : "View relief inventory locations and current depot stock."
        }
      />

      {!canUpdateInventory && (
        <div className="note-box">
          Inventory is read-only for this account.
          Only an Administrator can update
          depot resource quantities.
        </div>
      )}

      <ErrorBlock error={error} />

      {loading && (
        <LoadingBlock
          text="Loading Indian resource depots..."
        />
      )}

      {data && (
        <>
          <div className="metrics-grid">
            <MetricCard
              label="Relief Depots"
              value={data.depot_count}
            />

            <MetricCard
              label="States Covered"
              value={data.state_count || states.length}
            />

            <MetricCard
              label="Depots per State"
              value={data.depots_per_state || 3}
            />

            <MetricCard
              label="Food Packets"
              value={Number(
                data.national_totals
                  ?.food_packets || 0
              ).toLocaleString()}
            />

            <MetricCard
              label="Water"
              value={`${Number(
                data.national_totals
                  ?.water_litres || 0
              ).toLocaleString()} L`}
            />

            <MetricCard
              label="Medical Kits"
              value={Number(
                data.national_totals
                  ?.medical_kits || 0
              ).toLocaleString()}
            />
          </div>

          <div className="inventory-layout">
            <section className="panel inventory-map-panel">
              <div className="panel-heading">
                <div>
                  <h3>
                    Prototype Depot Network —
                    India
                  </h3>

                  <p>
                    Click a depot marker to
                    inspect its inventory
                  </p>
                </div>
              </div>

              <DepotMap
                depots={visibleDepots}
                selectedId={
                  selected?.depot_id
                }
                onSelect={setSelectedId}
              />
            </section>

            <section className="panel selected-depot-panel">
              <div className="inventory-filter-grid">
                <label>
                  Select state

                  <select
                    value={selectedState}
                    onChange={(event) =>
                      setSelectedState(
                        event.target.value
                      )
                    }
                  >
                    <option value="ALL">
                      All States
                    </option>

                    {states.map(
                      (state) => (
                        <option
                          key={state}
                          value={state}
                        >
                          {state}
                        </option>
                      )
                    )}
                  </select>
                </label>

                <label>
                  Select district depot

                  <select
                    value={
                      selected?.depot_id ||
                      ""
                    }
                    onChange={(event) =>
                      setSelectedId(
                        event.target.value
                      )
                    }
                  >
                    {visibleDepots.map(
                      (depot) => (
                        <option
                          key={
                            depot.depot_id
                          }
                          value={
                            depot.depot_id
                          }
                        >
                          {depot.district ||
                            depot.city}
                          {" · "}
                          {depot.city}
                        </option>
                      )
                    )}
                  </select>
                </label>
              </div>

              {selected && (
                <>
                  <div className="selected-depot-head">
                    <div>
                      <h2>
                        {selected.name}
                      </h2>

                      <p>
                        {selected.district ||
                          selected.city}
                        {" District · "}
                        {selected.city},{" "}
                        {selected.state}, India
                      </p>

                      <small>
                        {Number(
                          selected.latitude
                        ).toFixed(4)}
                        ,{" "}
                        {Number(
                          selected.longitude
                        ).toFixed(4)}
                        {" · "}
                        {selected.region}
                      </small>
                    </div>

                    <StatusBadge
                      value={selected.status}
                    />
                  </div>

                  <div className="depot-resource-grid">
                    {Object.entries(
                      selected.resources || {}
                    ).map(
                      ([key, value]) => (
                        <div
                          className="depot-resource-card"
                          key={key}
                        >
                          <span>
                            {labels[key] ||
                              key}
                          </span>

                          <strong>
                            {Number(
                              value
                            ).toLocaleString()}
                          </strong>

                          <StatusBadge
                            value={
                              selected
                                .resource_status?.[
                                key
                              ] ||
                              "AVAILABLE"
                            }
                          />

                          {canUpdateInventory && (
                            <>
                              {editing ===
                              key ? (
                                <div className="mini-editor">
                                  <input
                                    type="number"
                                    min="0"
                                    value={qty}
                                    onChange={(
                                      event
                                    ) =>
                                      setQty(
                                        event
                                          .target
                                          .value
                                      )
                                    }
                                  />

                                  <input
                                    value={reason}
                                    onChange={(
                                      event
                                    ) =>
                                      setReason(
                                        event
                                          .target
                                          .value
                                      )
                                    }
                                    placeholder="Reason"
                                  />

                                  <div>
                                    <button
                                      className="primary-button"
                                      onClick={() =>
                                        save(
                                          key
                                        )
                                      }
                                      disabled={
                                        saving
                                      }
                                    >
                                      {saving
                                        ? "Saving..."
                                        : "Save"}
                                    </button>

                                    <button
                                      className="small-button"
                                      onClick={() =>
                                        setEditing(
                                          null
                                        )
                                      }
                                    >
                                      Cancel
                                    </button>
                                  </div>
                                </div>
                              ) : (
                                <button
                                  className="inventory-edit-button"
                                  onClick={() => {
                                    setEditing(
                                      key
                                    );
                                    setQty(
                                      value
                                    );
                                    setReason(
                                      "Inventory update"
                                    );
                                  }}
                                >
                                  Update
                                </button>
                              )}
                            </>
                          )}
                        </div>
                      )
                    )}
                  </div>
                </>
              )}
            </section>
          </div>

          <section className="panel compact-history">
            <div className="panel-heading">
              <div>
                <h3>
                  Recent Depot Inventory
                  Changes
                </h3>

                <p>
                  Latest six updates
                </p>
              </div>
            </div>

            {(data.history || [])
              .length ? (
              <div className="table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Depot</th>
                      <th>Resource</th>
                      <th>Change</th>
                      <th>New</th>
                      <th>Reason</th>
                    </tr>
                  </thead>

                  <tbody>
                    {data.history
                      .slice(0, 6)
                      .map(
                        (
                          history,
                          index
                        ) => (
                          <tr key={index}>
                            <td>
                              {history.depot_name ||
                                history.depot_id}
                            </td>

                            <td>
                              {labels[
                                history
                                  .resource
                              ] ||
                                history.resource}
                            </td>

                            <td
                              className={
                                Number(
                                  history.change
                                ) < 0
                                  ? "danger-text"
                                  : "success-text"
                              }
                            >
                              {Number(
                                history.change
                              ) > 0
                                ? `+${history.change}`
                                : history.change}
                            </td>

                            <td>
                              {Number(
                                history.new_quantity ||
                                  0
                              ).toLocaleString()}
                            </td>

                            <td>
                              {history.reason}
                            </td>
                          </tr>
                        )
                      )}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="state-box">
                No depot inventory
                changes yet.
              </div>
            )}
          </section>

          <div className="note-box">
            {data.note}
          </div>
        </>
      )}
    </div>
  );
}

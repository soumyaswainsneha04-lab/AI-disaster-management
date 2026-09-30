import {
  useEffect,
  useState,
} from "react";

import { apiFetch } from "../api";
import { useAuth } from "../auth/AuthContext";
import {
  PageHeader,
  DataContextStrip,
  EmergencyHelpCard,
} from "../components/Common";

const DISASTER_TYPES = [
  "Flood",
  "Cyclone",
  "Earthquake",
  "Wildfire",
  "Landslide",
];

export default function Profile() {
  const {
    user,
    changePassword,
  } = useAuth();

  const [currentPassword, setCurrentPassword] =
    useState("");

  const [newPassword, setNewPassword] =
    useState("");

  const [confirmPassword, setConfirmPassword] =
    useState("");

  const [message, setMessage] =
    useState("");

  const [error, setError] =
    useState("");

  const [saving, setSaving] =
    useState(false);

  const [prefsLoading, setPrefsLoading] =
    useState(true);

  const [prefs, setPrefs] =
    useState({
      home_label: "",
      home_latitude: null,
      home_longitude: null,
      state: "",
      district: "",
      alert_types: [],
      updated_at: null,
    });

  async function loadPreferences() {
    setPrefsLoading(true);

    try {
      const data = await apiFetch(
        "/profile/preferences"
      );

      setPrefs({
        ...prefs,
        ...(data.preferences || {}),
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setPrefsLoading(false);
    }
  }

  useEffect(() => {
    loadPreferences();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function submitPassword(event) {
    event.preventDefault();
    setMessage("");
    setError("");

    if (
      newPassword !== confirmPassword
    ) {
      setError(
        "New passwords do not match."
      );
      return;
    }

    setSaving(true);

    const result =
      await changePassword(
        currentPassword,
        newPassword
      );

    setSaving(false);

    if (!result.ok) {
      setError(result.message);
      return;
    }

    setMessage(
      "Password changed successfully."
    );

    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
  }

  function useCurrentLocation() {
    setError("");

    if (!navigator.geolocation) {
      setError(
        "Location access is not available in this browser."
      );
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setPrefs((current) => ({
          ...current,
          home_label:
            current.home_label ||
            "My saved location",
          home_latitude:
            position.coords.latitude,
          home_longitude:
            position.coords.longitude,
        }));
      },
      () => {
        setError(
          "Location permission was not available."
        );
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
      }
    );
  }

  function toggleAlert(type) {
    setPrefs((current) => {
      const selected =
        current.alert_types || [];

      return {
        ...current,
        alert_types:
          selected.includes(type)
            ? selected.filter(
                (item) =>
                  item !== type
              )
            : [
                ...selected,
                type,
              ],
      };
    });
  }

  async function savePreferences(event) {
    event.preventDefault();

    setSaving(true);
    setError("");
    setMessage("");

    try {
      const data = await apiFetch(
        "/profile/preferences",
        {
          method: "PUT",
          body: JSON.stringify({
            home_label:
              prefs.home_label || "",
            home_latitude:
              prefs.home_latitude,
            home_longitude:
              prefs.home_longitude,
            state:
              prefs.state || "",
            district:
              prefs.district || "",
            alert_types:
              prefs.alert_types || [],
          }),
        }
      );

      setPrefs(
        data.preferences || prefs
      );

      setMessage(
        "Location and alert preferences saved."
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="My Profile"
        subtitle="Manage your account, saved location and disaster-alert preferences."
      />

      <DataContextStrip
        mode="PERSONAL SETTINGS"
        source="Disaster AI India account"
        updatedAt={prefs.updated_at}
        status="Private to your account"
      />

      <EmergencyHelpCard compact />

      {error && (
        <div className="state-box error-box">
          {error}
        </div>
      )}

      {message && (
        <div className="state-box success-box">
          {message}
        </div>
      )}

      <div className="profile-grid">
        <section className="panel profile-card">
          <div className="profile-avatar-large">
            {(user?.name || "U")
              .split(" ")
              .map((part) => part[0])
              .slice(0, 2)
              .join("")}
          </div>

          <h3>{user?.name}</h3>

          <span className="profile-role">
            {String(
              user?.role || ""
            ).replaceAll("_", " ")}
          </span>

          <div className="profile-details">
            <div>
              <span>Email</span>
              <strong>
                {user?.email}
              </strong>
            </div>

            <div>
              <span>
                Operational region
              </span>
              <strong>
                {user?.region || "India"}
              </strong>
            </div>

            <div>
              <span>
                Account status
              </span>
              <strong>
                {user?.is_active
                  ? "ACTIVE"
                  : "INACTIVE"}
              </strong>
            </div>
          </div>
        </section>

        <section className="panel">
          <div className="panel-heading">
            <div>
              <h3>
                Saved Safety Location
              </h3>
              <p>
                Save your home or primary location so My Safety can open it quickly.
              </p>
            </div>
          </div>

          {prefsLoading ? (
            <div className="state-box">
              Loading preferences...
            </div>
          ) : (
            <form
              className="profile-preferences-form"
              onSubmit={savePreferences}
            >
              <label>
                Location name
                <input
                  value={
                    prefs.home_label ||
                    ""
                  }
                  onChange={(event) =>
                    setPrefs(
                      (current) => ({
                        ...current,
                        home_label:
                          event.target
                            .value,
                      })
                    )
                  }
                  placeholder="My Home"
                />
              </label>

              <label>
                State
                <input
                  value={
                    prefs.state || ""
                  }
                  onChange={(event) =>
                    setPrefs(
                      (current) => ({
                        ...current,
                        state:
                          event.target
                            .value,
                      })
                    )
                  }
                  placeholder="Odisha"
                />
              </label>

              <label>
                District
                <input
                  value={
                    prefs.district ||
                    ""
                  }
                  onChange={(event) =>
                    setPrefs(
                      (current) => ({
                        ...current,
                        district:
                          event.target
                            .value,
                      })
                    )
                  }
                  placeholder="Khordha"
                />
              </label>

              <div className="saved-coordinate-box">
                <span>
                  Coordinates
                </span>

                <strong>
                  {prefs.home_latitude != null &&
                  prefs.home_longitude != null
                    ? `${Number(
                        prefs.home_latitude
                      ).toFixed(
                        5
                      )}, ${Number(
                        prefs.home_longitude
                      ).toFixed(5)}`
                    : "Not saved yet"}
                </strong>
              </div>

              <button
                type="button"
                className="small-button"
                onClick={useCurrentLocation}
              >
                ⌖ Use Current Location
              </button>

              <div className="alert-preference-box">
                <strong>
                  Disaster alerts I care about
                </strong>

                <div className="alert-checkbox-grid">
                  {DISASTER_TYPES.map(
                    (type) => (
                      <label
                        key={type}
                        className="alert-check"
                      >
                        <input
                          type="checkbox"
                          checked={(
                            prefs.alert_types ||
                            []
                          ).includes(type)}
                          onChange={() =>
                            toggleAlert(
                              type
                            )
                          }
                        />

                        <span>
                          {type}
                        </span>
                      </label>
                    )
                  )}
                </div>
              </div>

              <button
                className="primary-button"
                disabled={saving}
              >
                {saving
                  ? "Saving..."
                  : "Save Preferences"}
              </button>

              <small className="preference-note">
                Alert selections are stored for future notification support. This local prototype does not yet send SMS or push alerts.
              </small>
            </form>
          )}
        </section>

        <section className="panel">
          <div className="panel-heading">
            <div>
              <h3>
                Change Password
              </h3>

              <p>
                Your password is verified and updated by the FastAPI backend.
              </p>
            </div>
          </div>

          <form
            className="profile-password-form"
            onSubmit={
              submitPassword
            }
          >
            <label>
              Current password
              <input
                type="password"
                value={
                  currentPassword
                }
                onChange={(event) =>
                  setCurrentPassword(
                    event.target
                      .value
                  )
                }
                minLength={8}
                required
              />
            </label>

            <label>
              New password
              <input
                type="password"
                value={newPassword}
                onChange={(event) =>
                  setNewPassword(
                    event.target
                      .value
                  )
                }
                minLength={8}
                required
              />
            </label>

            <label>
              Confirm new password
              <input
                type="password"
                value={
                  confirmPassword
                }
                onChange={(event) =>
                  setConfirmPassword(
                    event.target
                      .value
                  )
                }
                minLength={8}
                required
              />
            </label>

            <button
              className="primary-button"
              disabled={saving}
            >
              {saving
                ? "Updating..."
                : "Change Password"}
            </button>
          </form>
        </section>
      </div>
    </div>
  );
}

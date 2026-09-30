import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useLanguage } from "../i18n/LanguageContext";
import LanguageSelector from "./LanguageSelector";

import {
  LayoutDashboard,
  ShieldCheck,
  Radio,
  Satellite,
  FileWarning,
  MapPinned,
  BrainCircuit,
  Boxes,
  SlidersHorizontal,
  Warehouse,
  Route,
  Truck,
  Signpost,
  ChartNoAxesCombined,
  PackageCheck,
  FlaskConical,
  Crosshair,
  ClipboardPenLine,
  Gauge,
  FileText,
  UsersRound,
  ClipboardList,
  LogOut,
} from "lucide-react";

const ALL_OPERATIONAL_ROLES = [
  "ADMIN",
  "RELIEF_COORDINATOR",
  "FIELD_TEAM",
  "CITIZEN",
];

const RESPONSE_STAFF_ROLES = [
  "ADMIN",
  "RELIEF_COORDINATOR",
  "FIELD_TEAM",
];

const GROUPS = [
  {
    label: "COMMAND CENTER",
    roles: ALL_OPERATIONAL_ROLES,
    items: [
      ["/", "Dashboard", LayoutDashboard],
      ["/safety", "My Safety", ShieldCheck],
      ["/feeds", "India Live Feeds", Radio],

      // LIVE EARTH
      ["/live-earth", "Live Earth", Satellite],

      ["/disasters", "Disaster Records", FileWarning],
      ["/operations-map", "Operations Map", MapPinned],
    ],
  },

  {
    label: "RESPONSE PLANNING",
    roles: ALL_OPERATIONAL_ROLES,
    items: [
      ["/prediction", "Resource Prediction", BrainCircuit],
      ["/allocation", "Resource Allocation", Boxes],
      ["/optimizer", "Optimization Planner", SlidersHorizontal],
      ["/inventory", "Resource Inventory", Warehouse],
      ["/eta", "Distance & ETA", Route],
      ["/routes", "Delivery Routes", Truck],
      ["/evacuation", "Evacuation Planner", Signpost],
      ["/transport", "Transport Recommendation", Truck],
      ["/logistics", "Logistics Analysis", ChartNoAxesCombined],
      ["/stock", "Stock Monitoring", PackageCheck],
      ["/scenario", "Scenario Simulator", FlaskConical],
    ],
  },

  {
    label: "RESPONSE OPERATIONS",
    roles: RESPONSE_STAFF_ROLES,
    items: [
      ["/missions", "Mission Control", Crosshair],
      ["/field-reports", "Field Reports", ClipboardPenLine],
    ],
  },

  {
    label: "INSIGHTS & REPORTS",
    roles: ["ADMIN"],
    items: [
      ["/confidence", "Prediction Confidence", Gauge],
      ["/explainability", "Model Explainability", BrainCircuit],
      ["/analytics", "Post-Event Analytics", ChartNoAxesCombined],
      ["/reports", "Situation Report", FileText],
    ],
  },

  {
    label: "ADMINISTRATION",
    roles: ["ADMIN"],
    items: [
      ["/admin/users", "User Management", UsersRound],
      ["/admin/audit", "Audit Log", ClipboardList],
    ],
  },
];

export default function Sidebar({
  mobileOpen = false,
  onClose = () => {},
}) {
  const { user, logout } = useAuth();
  const { t } = useLanguage();
  const navigate = useNavigate();

  const role = user?.role;

  const initials = (user?.name || "User")
    .split(" ")
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  function signOut() {
    logout();
    onClose();

    navigate("/login", {
      replace: true,
    });
  }

  return (
    <aside
      className={`sidebar ${
        mobileOpen ? "mobile-open" : ""
      }`}
    >
      {/* BRAND / MOBILE CLOSE */}
      <div className="sidebar-mobile-row">
        <div className="brand">
          <img
            src="/disaster-ai-icon.svg"
            alt="Disaster AI India"
            className="brand-logo-img"
            data-no-translate
          />

          <div>
            <h2 data-no-translate>
              Disaster AI India
            </h2>

            <p>
              {t("Emergency Response")}
            </p>
          </div>
        </div>

        <button
          className="sidebar-close-button"
          type="button"
          onClick={onClose}
          aria-label="Close navigation menu"
        >
          ×
        </button>
      </div>

      {/* NAVIGATION GROUPS */}
      {GROUPS
        .filter((group) =>
          group.roles.includes(role)
        )
        .map((group) => (
          <div
            className="nav-group"
            key={group.label}
          >
            <div className="sidebar-label">
              {t(group.label)}
            </div>

            <nav className="sidebar-menu">
              {group.items.map(
                ([to, name, Icon]) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={to === "/"}
                    onClick={onClose}
                    className={({ isActive }) =>
                      isActive
                        ? "menu-item active"
                        : "menu-item"
                    }
                  >
                    <span
                      className="menu-icon"
                      aria-hidden="true"
                    >
                      <Icon
                        size={19}
                        strokeWidth={1.9}
                      />
                    </span>

                    <span className="menu-text">
                      {t(name)}
                    </span>

                    {/* LIVE badge for Live Earth */}
                    {to === "/live-earth" && (
                      <span
                        className="menu-live-badge"
                        data-no-translate
                      >
                        LIVE
                      </span>
                    )}
                  </NavLink>
                )
              )}
            </nav>
          </div>
        ))}

      {/* LANGUAGE */}
      <div className="sidebar-language-block">
        <LanguageSelector />
      </div>

      {/* USER PROFILE */}
      <div className="sidebar-user">
        <button
          className="sidebar-profile-link"
          type="button"
          onClick={() => {
            onClose();
            navigate("/profile");
          }}
        >
          <div className="user-avatar">
            {initials}
          </div>

          <div className="user-copy">
            <strong>
              {user?.name || "User"}
            </strong>

            <span>
              {String(
                user?.role || ""
              ).replaceAll("_", " ")}
            </span>
          </div>
        </button>

        <button
          className="logout-button"
          type="button"
          onClick={signOut}
          title="Sign out"
          aria-label="Sign out"
        >
          <LogOut
            size={18}
            strokeWidth={1.9}
          />
        </button>
      </div>

      {/* FOOTER */}
      <div className="sidebar-footer">
        <span className="status-dot" />
        {t("Secure India Access")}
      </div>
    </aside>
  );
}
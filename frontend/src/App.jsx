import { lazy, Suspense, useState } from "react";
import "./App.css";

import {
  BrowserRouter,
  Routes,
  Route,
} from "react-router-dom";

import {
  AuthProvider,
  useAuth,
} from "./auth/AuthContext";

import ProtectedRoute from "./components/ProtectedRoute";
import Sidebar from "./components/Sidebar";
import LanguageSelector from "./components/LanguageSelector";
import NotificationBell from "./components/NotificationBell";

// Main pages
const Dashboard = lazy(() => import("./pages/Dashboard"));
const CitizenSafety = lazy(() => import("./pages/CitizenSafety"));
const DisasterRecords = lazy(() => import("./pages/DisasterRecords"));
const Login = lazy(() => import("./pages/Login"));
const Signup = lazy(() => import("./pages/Signup"));
const ForgotPassword = lazy(() => import("./pages/ForgotPassword"));
const NotFound = lazy(() => import("./pages/NotFound"));
const AccessDenied = lazy(() => import("./pages/AccessDenied"));

// Operational pages
const OptimizationPlanner = lazy(() =>
  import("./pages/OptimizationPlanner")
);

const ResourceInventory = lazy(() =>
  import("./pages/ResourceInventory")
);

const LiveFeeds = lazy(() =>
  import("./pages/LiveFeeds")
);

const LiveEarth = lazy(() =>
  import("./pages/LiveEarth")
);

const OperationsMap = lazy(() =>
  import("./pages/OperationsMap")
);

const FieldReports = lazy(() =>
  import("./pages/FieldReports")
);

const MissionControl = lazy(() =>
  import("./pages/MissionControl")
);

const RoutePlanner = lazy(() =>
  import("./pages/RoutePlanner")
);

const ScenarioSimulator = lazy(() =>
  import("./pages/ScenarioSimulator")
);

const AnalyticsReports = lazy(() =>
  import("./pages/AnalyticsReports")
);

const SituationReport = lazy(() =>
  import("./pages/SituationReport")
);

const UserManagement = lazy(() =>
  import("./pages/UserManagement")
);

const AuditLog = lazy(() =>
  import("./pages/AuditLog")
);

const Profile = lazy(() =>
  import("./pages/Profile")
);

// Generic feature pages
const GenericFeaturePage = lazy(() =>
  import("./pages/FeaturePages").then((module) => ({
    default: module.GenericFeaturePage,
  }))
);

const DistanceETA = lazy(() =>
  import("./pages/FeaturePages").then((module) => ({
    default: module.DistanceETA,
  }))
);

const ModelExplainability = lazy(() =>
  import("./pages/FeaturePages").then((module) => ({
    default: module.ModelExplainability,
  }))
);


// ---------------------------------------------------------
// ADMIN ONLY
// ---------------------------------------------------------

function AdminOnly({ children }) {
  const { user } = useAuth();

  return user?.role === "ADMIN"
    ? children
    : <AccessDenied />;
}


// ---------------------------------------------------------
// STAFF ONLY
// ---------------------------------------------------------

function StaffOnly({ children }) {
  const { user } = useAuth();

  const allowed = [
    "ADMIN",
    "RELIEF_COORDINATOR",
    "FIELD_TEAM",
  ].includes(user?.role);

  return allowed
    ? children
    : <AccessDenied />;
}


// ---------------------------------------------------------
// PROTECTED APPLICATION SHELL
// ---------------------------------------------------------

function ProtectedShell() {
  const [mobileMenuOpen, setMobileMenuOpen] =
    useState(false);

  return (
    <ProtectedRoute>

      <div className="app-shell">

        {/* -------------------------------------------------
            MOBILE TOP BAR
        ------------------------------------------------- */}

        <header className="mobile-topbar">

          <button
            className="mobile-menu-button"
            type="button"
            aria-label="Open navigation menu"
            aria-expanded={mobileMenuOpen}
            onClick={() => setMobileMenuOpen(true)}
          >
            ☰
          </button>


          <div className="mobile-brand">

            <img
              src="/disaster-ai-icon.svg"
              alt="Disaster AI India"
              className="brand-logo-img"
              data-no-translate
            />

            <div>

              <strong data-no-translate>
                Disaster AI India
              </strong>

              <span>
                Emergency Response
              </span>

            </div>

          </div>


          <div className="mobile-topbar-actions">
            <NotificationBell compact />
            <LanguageSelector compact />
          </div>

        </header>


        {/* -------------------------------------------------
            SIDEBAR
        ------------------------------------------------- */}

        <Sidebar
          mobileOpen={mobileMenuOpen}
          onClose={() => setMobileMenuOpen(false)}
        />


        {/* -------------------------------------------------
            MOBILE SIDEBAR OVERLAY
        ------------------------------------------------- */}

        {mobileMenuOpen && (
          <button
            className="sidebar-overlay"
            type="button"
            aria-label="Close navigation menu"
            onClick={() =>
              setMobileMenuOpen(false)
            }
          />
        )}

        {/* -------------------------------------------------
            DESKTOP NOTIFICATION BAR
        ------------------------------------------------- */}

        <header className="desktop-topbar">
          <div className="desktop-topbar-copy">
            <strong>India Emergency Response</strong>
            <span>Live disaster notifications</span>
          </div>

          <NotificationBell />
        </header>


        {/* -------------------------------------------------
            MAIN CONTENT
        ------------------------------------------------- */}

        <main className="main-content">

          <Suspense
            fallback={
              <div className="state-box">
                Loading module…
              </div>
            }
          >

            <Routes>

              {/* =================================================
                  SHARED OPERATIONAL APPLICATION
                  Citizen + Coordinator + Field Team + Admin
              ================================================= */}

              <Route
                path="/"
                element={<Dashboard />}
              />

              <Route
                path="/safety"
                element={<CitizenSafety />}
              />

              <Route
                path="/profile"
                element={<Profile />}
              />

              <Route
                path="/feeds"
                element={<LiveFeeds />}
              />

              <Route
                path="/live-earth"
                element={<LiveEarth />}
              />

              <Route
                path="/disasters"
                element={<DisasterRecords />}
              />

              <Route
                path="/operations-map"
                element={<OperationsMap />}
              />


              {/* =================================================
                  AI RESPONSE PLANNING
              ================================================= */}

              <Route
                path="/prediction"
                element={
                  <GenericFeaturePage
                    kind="prediction"
                  />
                }
              />

              <Route
                path="/allocation"
                element={
                  <GenericFeaturePage
                    kind="allocation"
                  />
                }
              />

              <Route
                path="/optimizer"
                element={<OptimizationPlanner />}
              />

              <Route
                path="/inventory"
                element={<ResourceInventory />}
              />

              <Route
                path="/eta"
                element={<DistanceETA />}
              />

              <Route
                path="/routes"
                element={<RoutePlanner />}
              />

              <Route
                path="/evacuation"
                element={
                  <GenericFeaturePage
                    kind="evacuation"
                  />
                }
              />

              <Route
                path="/transport"
                element={
                  <GenericFeaturePage
                    kind="transport"
                  />
                }
              />

              <Route
                path="/logistics"
                element={
                  <GenericFeaturePage
                    kind="logistics"
                  />
                }
              />

              <Route
                path="/stock"
                element={
                  <GenericFeaturePage
                    kind="stock"
                  />
                }
              />

              <Route
                path="/scenario"
                element={<ScenarioSimulator />}
              />


              {/* =================================================
                  STAFF ONLY
              ================================================= */}

              <Route
                path="/missions"
                element={
                  <StaffOnly>
                    <MissionControl />
                  </StaffOnly>
                }
              />

              <Route
                path="/field-reports"
                element={
                  <StaffOnly>
                    <FieldReports />
                  </StaffOnly>
                }
              />


              {/* =================================================
                  ADMIN ONLY — INSIGHTS & REPORTS
              ================================================= */}

              <Route
                path="/confidence"
                element={
                  <AdminOnly>
                    <GenericFeaturePage
                      kind="confidence"
                    />
                  </AdminOnly>
                }
              />

              <Route
                path="/explainability"
                element={
                  <AdminOnly>
                    <ModelExplainability />
                  </AdminOnly>
                }
              />

              <Route
                path="/analytics"
                element={
                  <AdminOnly>
                    <AnalyticsReports />
                  </AdminOnly>
                }
              />

              <Route
                path="/reports"
                element={
                  <AdminOnly>
                    <SituationReport />
                  </AdminOnly>
                }
              />


              {/* =================================================
                  ADMIN ONLY — SYSTEM ADMINISTRATION
              ================================================= */}

              <Route
                path="/admin/users"
                element={
                  <AdminOnly>
                    <UserManagement />
                  </AdminOnly>
                }
              />

              <Route
                path="/admin/audit"
                element={
                  <AdminOnly>
                    <AuditLog />
                  </AdminOnly>
                }
              />


              {/* =================================================
                  404
              ================================================= */}

              <Route
                path="*"
                element={<NotFound />}
              />

            </Routes>

          </Suspense>

        </main>

      </div>

    </ProtectedRoute>
  );
}


// ---------------------------------------------------------
// ROOT APP
// ---------------------------------------------------------

export default function App() {

  return (

    <BrowserRouter>

      <AuthProvider>

        <Routes>

          {/* =================================================
              AUTHENTICATION
          ================================================= */}

          <Route
            path="/login"
            element={<Login />}
          />

          <Route
            path="/signup"
            element={<Signup />}
          />

          <Route
            path="/forgot-password"
            element={<ForgotPassword />}
          />


          {/* =================================================
              PUBLIC EMERGENCY SAFETY
          ================================================= */}

          <Route
            path="/public-safety"
            element={
              <CitizenSafety publicMode />
            }
          />


          {/* =================================================
              PROTECTED APPLICATION
          ================================================= */}

          <Route
            path="/*"
            element={<ProtectedShell />}
          />

        </Routes>

      </AuthProvider>

    </BrowserRouter>
  );
}
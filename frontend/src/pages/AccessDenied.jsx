import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function AccessDenied() {
  const { user } = useAuth();
  return (
    <div className="access-denied-page">
      <div className="access-denied-card">
        <span>ACCESS RESTRICTED</span>
        <h1>Permission required</h1>
        <p>
          Your role ({String(user?.role || "USER").replaceAll("_", " ")}) does not have permission to open this module.
        </p>
        <Link to="/" className="primary-button access-denied-link">Return to Dashboard</Link>
      </div>
    </div>
  );
}

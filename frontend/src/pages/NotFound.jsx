import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="not-found-page">
      <div className="not-found-card">
        <span>404</span>
        <h1>Page not found</h1>
        <p>The requested Disaster AI page does not exist.</p>
        <Link to="/" className="primary-button not-found-link">Return to Dashboard</Link>
      </div>
    </div>
  );
}

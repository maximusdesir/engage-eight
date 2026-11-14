// Top bar shared by the public pages (landing and quiz). On phones it collapses
// to the red brand mark plus the account button.
import { Link } from "react-router-dom";
import { useStore } from "../useStore";

export default function SiteNav({ page }: { page: "home" | "quiz" }) {
  const { user } = useStore();
  const ways = page === "home" ? "#ways" : "/#ways";
  return (
    <header className="nav">
      <Link className="nav-mark" to="/" aria-label="Engage Eight home" />
      <nav className="nav-links" aria-label="Main">
        {page === "quiz" && (
          <Link className="nav-link" to="/">
            Home
          </Link>
        )}
        <Link className="nav-link" to="/quiz" aria-current={page === "quiz" ? "page" : undefined}>
          The quiz
        </Link>
        <a className="nav-link" href={ways}>
          Scout a team
        </a>
        <a className="nav-link" href={ways}>
          Use your film
        </a>
      </nav>
      <div className="nav-actions">
        {user ? (
          <Link className="btn btn-sm btn-line" to="/tendencies">
            Open the app
          </Link>
        ) : (
          <Link className="btn btn-sm btn-line" to="/login">
            Sign in
          </Link>
        )}
        {page === "home" && (
          <Link className="btn btn-sm btn-light nav-quiz" to="/quiz">
            Take the quiz
          </Link>
        )}
      </div>
    </header>
  );
}

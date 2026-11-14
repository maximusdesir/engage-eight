// Top bar shared by the public pages (landing, quiz, sign in). On phones it
// collapses to the red brand mark plus the account button.
import { Link } from "react-router-dom";
import { useStore } from "../useStore";

export default function SiteNav({ page }: { page: "home" | "quiz" | "login" }) {
  const { user } = useStore();
  const ways = page === "home" ? "#ways" : "/#ways";
  return (
    <header className="nav">
      <Link className="nav-mark" to="/" aria-label="Engage Eight home" />
      <nav className="nav-links" aria-label="Main">
        {page !== "home" && (
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
          page !== "login" && (
            <Link className="btn btn-sm btn-line" to="/login">
              Sign in
            </Link>
          )
        )}
        {page !== "quiz" && (
          // On phones the landing hero repeats this button, so it hides there;
          // on the sign-in page it's the only one, so it stays.
          <Link
            className={`btn btn-sm btn-light nav-quiz${page === "login" ? " nav-quiz-keep" : ""}`}
            to="/quiz"
          >
            Take the quiz
          </Link>
        )}
      </div>
    </header>
  );
}

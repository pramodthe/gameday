import { useState } from "react";
import { CoachBoard } from "./components/CoachBoard";
import { MirrorView } from "./components/MirrorView";

export default function App() {
  const [view, setView] = useState<"mirror" | "coach">("mirror");
  return (
    <div className="app">
      <nav className="topnav">
        <div className="logo">
          Ready<span>Room</span>
        </div>
        <div className="tabs">
          <button className={view === "mirror" ? "on" : ""} onClick={() => setView("mirror")}>
            Athlete Mirror
          </button>
          <button className={view === "coach" ? "on" : ""} onClick={() => setView("coach")}>
            Coach Board
          </button>
        </div>
      </nav>
      <main className="stage">{view === "mirror" ? <MirrorView /> : <CoachBoard />}</main>
    </div>
  );
}

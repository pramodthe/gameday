import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.tsx";

// StrictMode intentionally omitted: this app opens a WebSocket and camera stream
// on mount, and double-invocation in dev causes duplicate connections.
createRoot(document.getElementById("root")!).render(<App />);

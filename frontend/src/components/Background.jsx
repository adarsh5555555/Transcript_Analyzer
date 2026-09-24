import "./Background.css";

// Render once at the top of <App />. Page content needs position:relative and
// z-index >= 1 to sit above the background.
export default function Background() {
  return (
    <>
      <div className="matte-background" aria-hidden="true">
        <div className="color-atmosphere" />
        <div className="matte-diffusion" />
        <div className="paper-grain-overlay" />
      </div>
      <div className="grain" aria-hidden="true" />
    </>
  );
}

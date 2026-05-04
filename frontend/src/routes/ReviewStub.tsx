import { Link } from "react-router-dom";

export default function ReviewStub() {
  return (
    <div className="fade-in">
      <h2>Repaso SRS</h2>
      <p className="muted">
        Próximamente: las palabras que añadiste a tu deck volverán cuando tu cerebro esté a punto de
        olvidarlas.
      </p>
      <Link to="/" className="btn btn-ghost">
        ← Volver
      </Link>
    </div>
  );
}

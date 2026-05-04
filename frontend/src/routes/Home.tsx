import Card from "../components/Card";
import "./Home.css";

export default function Home() {
  return (
    <div className="home fade-in">
      <p className="home__lead">
        Elige <strong>una</strong> de las tres. Sesiones cortas, sin presión de racha.
      </p>

      <div className="home__menu">
        <Card
          to="/story/new"
          emoji="📖"
          title="Nueva historia"
          subtitle="Una micro-historia a tu nivel — leer, escuchar, marcar palabras"
          duration="3–5 min"
          variant="primary"
        />
        <Card
          to="/review"
          emoji="🧠"
          title="Repaso SRS"
          subtitle="Las palabras que tu cerebro está a punto de olvidar"
          duration="5 min"
        />
        <Card
          to="/chat"
          emoji="💬"
          title="Hablar con Klara"
          subtitle="Conversación libre en alemán con Klara — corregida, sin juicio"
          duration="abierto"
        />
      </div>
    </div>
  );
}

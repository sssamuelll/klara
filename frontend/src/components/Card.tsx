import { Link } from "react-router-dom";
import "./Card.css";

interface CardProps {
  to: string;
  title: string;
  subtitle: string;
  emoji: string;
  duration?: string;
  variant?: "primary" | "default";
}

export default function Card({ to, title, subtitle, emoji, duration, variant }: CardProps) {
  return (
    <Link to={to} className={`menu-card ${variant === "primary" ? "menu-card--primary" : ""}`}>
      <div className="menu-card__icon" aria-hidden>
        {emoji}
      </div>
      <div className="menu-card__body">
        <div className="menu-card__title">{title}</div>
        <div className="menu-card__sub">{subtitle}</div>
      </div>
      {duration && <div className="menu-card__duration">{duration}</div>}
    </Link>
  );
}

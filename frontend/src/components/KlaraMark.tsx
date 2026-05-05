interface Props {
  size?: number;
  speaking?: boolean;
  italic?: boolean;
}

export default function KlaraMark({ size = 24, speaking = false, italic = true }: Props) {
  return (
    <span
      className="klara-mark"
      data-speaking={speaking}
      style={{
        width: size,
        height: size,
        fontSize: size,
        fontStyle: italic ? "italic" : "normal",
      }}
      aria-hidden="true"
    >
      <span className="glyph">K</span>
    </span>
  );
}

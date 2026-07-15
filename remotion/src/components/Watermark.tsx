export const Watermark = () => {
  return (
    <div
      style={{
        position: "absolute",
        top: "62%",
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        zIndex: 200,
      }}
    >
      <span
        style={{
          fontSize: 28,
          fontWeight: 700,
          fontFamily: '"Montserrat", sans-serif',
          color: "rgba(255,255,255,0.7)",
          textShadow: "0 2px 12px rgba(0,0,0,0.9), 0 0 20px rgba(0,0,0,0.5)",
          letterSpacing: 1,
        }}
      >
        @yarnstoryteller
      </span>
    </div>
  );
};

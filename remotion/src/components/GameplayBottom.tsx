import { AbsoluteFill, useCurrentFrame, spring } from "remotion";

interface Props {
  isSpeaking: boolean;
}

export const GameplayBottom = ({ isSpeaking }: Props) => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      {/* Dim overlay that pulses with narration */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: isSpeaking
            ? "rgba(0,0,0,0.15)"
            : "rgba(0,0,0,0.05)",
          transition: "background 0.2s",
        }}
      />
      {/* Watermark */}
      <div
        style={{
          position: "absolute",
          bottom: 12,
          right: 16,
          fontSize: 12,
          fontFamily: "sans-serif",
          color: "rgba(255,255,255,0.25)",
          zIndex: 10,
        }}
      >
        Story Factory
      </div>
    </AbsoluteFill>
  );
};

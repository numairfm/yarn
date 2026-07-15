import { useCurrentFrame, useVideoConfig, spring } from "remotion";
import type { WordTimestamp } from "../types";

interface Props {
  words: WordTimestamp[];
}

const COLORS = {
  inactive: "rgba(255,255,255,0.4)",
  active: "#FFD700",
  passed: "rgba(255,255,255,0.9)",
};

const WORDS_PER_LINE = 6;

export const KaraokeSubtitles = ({ words }: Props) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentMs = (frame / fps) * 1000;

  if (!words.length) return null;

  // Guard: if past the very last word, hide subtitles entirely
  if (currentMs > words[words.length - 1].end) {
    return null;
  }

  // Guard: if before the very first word starts speaking, hide subtitles entirely
  if (currentMs < words[0].start) {
    return null;
  }

  // Find active word
  const activeWordIdx = words.findIndex(
    (w) => currentMs >= w.start && currentMs <= w.end
  );

  // If in a pause/gap, find the last completed word
  let currentIdx = activeWordIdx;
  if (currentIdx === -1) {
    const passedIdx = words.findIndex((w) => currentMs < w.start);
    currentIdx = passedIdx === -1 ? words.length - 1 : Math.max(0, passedIdx - 1);
  }

  // Calculate which line/chunk we are on
  const activeLineIdx = Math.floor(currentIdx / WORDS_PER_LINE);
  
  // Slice words into groups of 6 (stable lines)
  const lines: WordTimestamp[][] = [];
  for (let i = 0; i < words.length; i += WORDS_PER_LINE) {
    lines.push(words.slice(i, i + WORDS_PER_LINE));
  }

  const visibleWords = lines[activeLineIdx] || [];

  return (
    <div
      style={{
        position: "absolute",
        top: "50%",
        left: 0,
        right: 0,
        transform: "translateY(-50%)",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        flexWrap: "wrap",
        padding: "20px 40px",
        gap: 12,
        zIndex: 100,
      }}
    >
      {visibleWords.map((w) => {
        // Find global word index to check active/passed status
        const globalIdx = words.findIndex((x) => x.start === w.start && x.end === w.end);
        const isActive = globalIdx === activeWordIdx;
        const isPassed = globalIdx < currentIdx || (globalIdx === currentIdx && currentMs > w.end);

        const scale = isActive
          ? spring({
              frame: frame - (w.start / 1000) * fps,
              fps,
              config: { damping: 10, stiffness: 220 },
            }) * 0.15 + 1
          : 1;

        const color = isActive
          ? COLORS.active
          : isPassed
          ? COLORS.passed
          : COLORS.inactive;

        return (
          <span
            key={globalIdx}
            style={{
              fontSize: 58,
              fontWeight: 900,
              fontFamily: '"Montserrat", sans-serif',
              color,
              display: "inline-block",
              transform: `scale(${scale})`,
              lineHeight: 1.2,
              textTransform: "uppercase",
              textShadow: isActive
                ? "-3px -3px 0 #000, 3px -3px 0 #000, -3px 3px 0 #000, 3px 3px 0 #000, -3px 0px 0 #000, 3px 0px 0 #000, 0px -3px 0 #000, 0px 3px 0 #000, 0 6px 16px rgba(0,0,0,0.8)"
                : "-2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000, 2px 2px 0 #000, -2px 0px 0 #000, 2px 0px 0 #000, 0px -2px 0 #000, 0px 2px 0 #000, 0 4px 12px rgba(0,0,0,0.6)",
              transition: "color 0.08s",
            }}
          >
            {w.word}
          </span>
        );
      })}
    </div>
  );
};

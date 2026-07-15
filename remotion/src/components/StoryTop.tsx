import { useCurrentFrame, useVideoConfig, interpolate, spring } from "remotion";

interface Props {
  title: string;
  subreddit?: string;
  partNumber?: number;
  titleEndMs?: number;
}

const RedditLogo = () => (
  <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
    <circle cx="16" cy="16" r="16" fill="#FF4500" />
    <path
      d="M26 16c0-1.1-.9-2-2-2-.5 0-1 .2-1.3.5-1.3-.9-3-1.4-4.9-1.5l.8-3.8 2.6.6c0 .7.6 1.3 1.3 1.3.7 0 1.3-.6 1.3-1.3 0-.7-.6-1.3-1.3-1.3-.5 0-.9.3-1.1.7l-3-.7c-.1 0-.3.1-.3.2l-.9 4.3c-1.9.1-3.6.6-4.9 1.5-.3-.3-.8-.5-1.3-.5-1.1 0-2 .9-2 2 0 .8.4 1.4 1.1 1.7 0 .2-.1.4-.1.6 0 2.5 2.9 4.5 6.5 4.5s6.5-2 6.5-4.5c0-.2 0-.4-.1-.6.7-.3 1.1-.9 1.1-1.7zM11.5 17c0-.7.6-1.3 1.3-1.3.7 0 1.3.6 1.3 1.3 0 .7-.6 1.3-1.3 1.3-.7 0-1.3-.6-1.3-1.3zm7.4 3.2c-.9.9-2.6 1-2.9 1s-2-.1-2.9-1c-.1-.1-.1-.3 0-.4.1-.1.3-.1.4 0 .6.6 1.8.8 2.5.8s1.9-.2 2.5-.8c.1-.1.3-.1.4 0 .1.1.1.3 0 .4zm.3-1.9c-.7 0-1.3-.6-1.3-1.3 0-.7.6-1.3 1.3-1.3.7 0 1.3.6 1.3 1.3 0 .7-.6 1.3-1.3 1.3z"
      fill="#fff"
    />
  </svg>
);

export const StoryTop = ({ title, subreddit, partNumber, titleEndMs }: Props) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const fadeIn = spring({ frame, fps, config: { damping: 20 } });

  const fadeOutStart = titleEndMs ? ((titleEndMs + 2000) / 1000) * fps : 30 * fps;
  const fadeDuration = 1.5 * fps;
  const opacity = interpolate(
    frame,
    [0, 10, fadeOutStart, fadeOutStart + fadeDuration],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const translateY = interpolate(
    frame,
    [fadeOutStart, fadeOutStart + fadeDuration],
    [0, -30],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const showPart = partNumber && partNumber > 1;

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "flex-end",
        alignItems: "center",
        padding: "0px 30px 100px 30px",
        background: "transparent",
        opacity: fadeIn * opacity,
        transform: `translateY(${translateY}px)`,
      }}
    >
      <div
        style={{
          width: "85%",
          maxWidth: 920,
          background: "#fff",
          borderRadius: 16,
          padding: "32px 28px",
          boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
          display: "flex",
          flexDirection: "column",
          gap: 16,
          position: "relative",
        }}
      >
        {/* Reddit logo + subreddit */}
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <RedditLogo />
          {subreddit && (
            <span
              style={{
                fontSize: 16,
                fontWeight: 600,
                color: "#FF4500",
                fontFamily: '"IBM Plex Sans", "Segoe UI", sans-serif',
              }}
            >
              r/{subreddit}
            </span>
          )}
        </div>

        {/* Title */}
        <h1
          style={{
            fontSize: 32,
            fontWeight: 700,
            color: "#1a1a1b",
            textAlign: "left",
            margin: 0,
            lineHeight: 1.3,
            fontFamily: '"IBM Plex Sans", "Segoe UI", sans-serif',
          }}
        >
          {title}
        </h1>

        {/* Part badge */}
        {showPart && (
          <div
            style={{
              position: "absolute",
              top: 16,
              right: 16,
              padding: "4px 12px",
              borderRadius: 12,
              background: "#FF4500",
              color: "#fff",
              fontSize: 14,
              fontWeight: 700,
              fontFamily: '"IBM Plex Sans", "Segoe UI", sans-serif',
            }}
          >
            Part {partNumber}
          </div>
        )}
      </div>
    </div>
  );
};

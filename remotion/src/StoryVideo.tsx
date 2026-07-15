import { AbsoluteFill, Audio, OffthreadVideo } from "remotion";
import { StoryTop } from "./components/StoryTop";
import { KaraokeSubtitles } from "./components/KaraokeSubtitles";
import { Watermark } from "./components/Watermark";
import type { InputProps } from "./types";

export const StoryVideo = (props: InputProps) => {
  const { narrationPath, words, storyTitle, brollClip, subreddit, partNumber, titleEndMs, videoStartFrame } = props;

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@900&display=swap');
      `}</style>
      {/* Fullscreen gameplay background */}
      <div style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
        {brollClip ? (
          <OffthreadVideo
            src={brollClip}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
            muted
            startFrom={videoStartFrame || 0}
          />
        ) : (
          <div
            style={{
              width: "100%",
              height: "100%",
              background: "linear-gradient(135deg, #1a1a2e, #16213e)",
            }}
          />
        )}
      </div>

      {/* Story UI Card overlay in top half */}
      <div style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "50%", zIndex: 10 }}>
        <StoryTop
          title={storyTitle}
          subreddit={subreddit}
          partNumber={partNumber}
          titleEndMs={titleEndMs}
        />
      </div>

      <KaraokeSubtitles words={words} />
      <Watermark />
      <Audio src={narrationPath} />
    </AbsoluteFill>
  );
};

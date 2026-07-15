import { Composition, getInputProps } from "remotion";
import { StoryVideo } from "./StoryVideo";
import type { InputProps } from "./types";

export const RemotionRoot = () => {
  const props = getInputProps() as InputProps | Record<string, never>;

  if (!("narrationPath" in props)) {
    return (
      <div style={{ padding: 40, fontFamily: "sans-serif", color: "white", background: "#111" }}>
        <h2>Story Factory - Remotion Studio</h2>
        <p>Provide input props to preview: narrationPath, words, storyTitle, storyBody, brollClip</p>
      </div>
    );
  }

  return (
    <Composition
      id="StoryVideo"
      component={StoryVideo as any}
      durationInFrames={props.durationFrames || 30 * 90}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={props}
    />
  );
};

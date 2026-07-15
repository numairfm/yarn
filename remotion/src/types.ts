export interface WordTimestamp {
  word: string;
  start: number;
  end: number;
}

export interface InputProps {
  narrationPath: string;
  words: WordTimestamp[];
  storyTitle: string;
  storyBody: string;
  brollClip: string;
  durationFrames?: number;
  subreddit?: string;
  partNumber?: number;
  titleEndMs?: number;
  videoStartFrame?: number;
}

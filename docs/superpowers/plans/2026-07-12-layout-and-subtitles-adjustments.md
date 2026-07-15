# Layout & Subtitle Adjustments Plan

**Goal:** Change video layout to fullscreen gameplay with a floating Reddit card, improve subtitle readability (non-scrolling line-by-line, bold centered fonts), and fix edge cases.

**Architecture:** 
- `StoryVideo.tsx`: Renders B-roll as absolute 100% height background. Renders StoryTop card over top 50% with transparent wrapper.
- `StoryTop.tsx`: Uses transparent background wrapper so gameplay shows behind the white card.
- `KaraokeSubtitles.tsx`: Chunks words into stable lines (6 words/line). Swaps lines all-at-once instead of constant scrolling. Uses heavy Montserrat font, black stroke outline, and guards against end-of-video or pause glitches.

---

## Task 1: Fullscreen Gameplay & Card Overlay (`StoryVideo.tsx`)

- [ ] Modify `remotion/src/StoryVideo.tsx` to render the B-roll video across 100% of the viewport (top: 0, height: 100%).
- [ ] Render the `StoryTop` card in the top half as an absolute overlay.
- [ ] No more split screen (50% black top, 50% video bottom) — gameplay is now the full canvas background.

## Task 2: Stable Line-by-Line Karaoke Subtitles (`KaraokeSubtitles.tsx`)

- [ ] Modify `remotion/src/components/KaraokeSubtitles.tsx`.
- [ ] Chunk words into groups of 6 words (stable lines).
- [ ] Map the current time to the active line index:
  ```typescript
  const wordsPerLine = 6;
  let activeWordIdx = words.findIndex(w => currentMs >= w.start && currentMs <= w.end);
  if (activeWordIdx === -1) {
    // pause/gap: find last completed word
    const passedIdx = words.findIndex(w => currentMs < w.start);
    activeWordIdx = passedIdx === -1 ? words.length - 1 : Math.max(0, passedIdx - 1);
  }
  const activeLineIdx = Math.floor(activeWordIdx / wordsPerLine);
  ```
- [ ] Display only `lines[activeLineIdx]`. Since the line is static, text does not scroll or shake!
- [ ] Set font to `"Montserrat", "Arial Black", Impact, sans-serif`.
- [ ] Add thick text border: `WebkitTextStroke: "3px black"` for high readability over gameplay.
- [ ] Add guard: if `currentMs > words[words.length - 1].end`, return `null` (shows nothing during final pause).

## Task 3: Reddit Card Fade & Transparency (`StoryTop.tsx`)

- [ ] Modify `remotion/src/components/StoryTop.tsx`.
- [ ] Change wrapper background from solid linear-gradient to transparent `background: "transparent"` so the fullscreen gameplay is fully visible behind the white card.
- [ ] Maintain the white card background and shadow.
- [ ] Ensure fade-out interpolation properly hides the card after `titleEndMs`.

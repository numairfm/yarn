---
name: reddit-scraper
description: Scrape Reddit stories via agent-browser, evaluate them for YouTube/TikTok content creation potential, and output qualifying stories as individual text files organized by subreddit.
---

# Reddit Scraper

Scrapes stories from Reddit using `agent-browser --auto-connect`, evaluates each for content creation appeal (YouTube/TikTok), and outputs qualifying stories to `output/reddit-stories/<subreddit>/`.

## Output Structure

```
output/reddit-stories/
├── <subreddit>/
│   ├── 01-story-slug.md
│   ├── 02-story-slug.md
│   └── ...
```

Each file contains one story in this exact format:

```
- subreddit: r/<subreddit>
- content: <story text>
```

## File Naming

`NN-short-slug.md` where NN is a zero-padded sequence number and slug is a 2-4 word summary of the story.

## Content Creation Criteria

A story passes if it has:
- **Emotional hook**: rage, justice, surprise, heartwarming, drama
- **Narrative arc**: beginning → conflict → resolution
- **Relatability**: most people can see themselves in the situation
- **Debate potential**: comment sections would argue about who's right
- **Visual/storytelling potential**: works as a narrated video

## Target Subreddits

- r/AmItheAsshole — moral dilemmas, drama
- r/tifu — humor, relatable mistakes
- r/relationship_advice — relationship drama
- r/entitledparents — outrage bait
- r/prorevenge — satisfaction narratives
- r/AskReddit — general stories
- r/confessions — raw personal stories

## Scraping Workflow

1. Navigate: `agent-browser --auto-connect open "https://old.reddit.com/r/<subreddit>/top/?t=week"`
2. Snapshot: `agent-browser --auto-connect snapshot -i -c` to find post links
3. Click into each promising post: `agent-browser --auto-connect click @eN`
4. Wait: `agent-browser --auto-connect wait --load networkidle`
5. Read content: `agent-browser --auto-connect get text ".entry .usertext-body"`
6. Go back: `agent-browser --auto-connect open "https://old.reddit.com/r/<subreddit>/top/?t=week"`
7. Repeat for next post

## Evaluation

For each scraped story, weigh it against the criteria. If it passes, write it as an individual file. Skip stories that are too short, lack narrative, or aren't compelling for video content.
NEVER EVER EVER SHORTEN IT. JUST COPY THE EXACT CONTENTS
## Requirements

- `agent-browser` installed and Chrome running with `--auto-connect`
- At least 10 qualifying stories total across all subreddits
- Stories must be unique (no duplicates across subreddits)

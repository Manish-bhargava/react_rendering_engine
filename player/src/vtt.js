// A small WebVTT reader.
//
// The narration plays through `new Audio()` rather than a <video> element, so there is
// no element to hang a <track> on and no TextTrack to read cues from. The player fetches
// the caption file itself, parses it here, and picks the cue for the current time.
//
// Caption files sit beside their audio and share its name: m1_1_02_base.mp3 pairs with
// m1_1_02_base.vtt. That convention is why no new key is needed in voiceover.json.

export const captionFileFor = (audioFile) => (audioFile ? audioFile.replace(/\.[^.]+$/, '.vtt') : null);

const stamp = (s) => {
  // hh:mm:ss.mmm or mm:ss.mmm
  const m = /^(?:(\d+):)?(\d{1,2}):(\d{2})(?:[.,](\d{1,3}))?$/.exec(s.trim());
  if (!m) return null;
  return (+(m[1] || 0)) * 3600 + (+m[2]) * 60 + (+m[3]) + (+(m[4] || 0)) / 1000;
};

/** Parse a WebVTT document into [{ start, end, text }], sorted by start. */
export function parseVtt(text) {
  const cues = [];
  // tolerate CRLF, a BOM and a NOTE/STYLE block
  const blocks = String(text).replace(/\r\n?/g, '\n').replace(/^﻿/, '').split(/\n{2,}/);
  for (const block of blocks) {
    const lines = block.split('\n').filter((l) => l.trim() !== '');
    if (!lines.length) continue;
    const head = lines[0].startsWith('WEBVTT') ? 1 : 0;
    const idx = lines.findIndex((l, i) => i >= head && l.includes('-->'));
    if (idx < 0) continue;
    const [a, b] = lines[idx].split('-->');
    const start = stamp(a);
    // a cue line may carry settings after the end time: "00:00:02.000 line:90%"
    const end = stamp((b || '').trim().split(/\s+/)[0] || '');
    if (start == null || end == null) continue;
    const body = lines.slice(idx + 1).join('\n').trim();
    if (body) cues.push({ start, end, text: body });
  }
  return cues.sort((x, y) => x.start - y.start);
}

/** The cue covering `t`, or null. Cues are assumed sorted and non-overlapping. */
export function cueAt(cues, t) {
  if (!cues || !cues.length) return null;
  let lo = 0;
  let hi = cues.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const c = cues[mid];
    if (t < c.start) hi = mid - 1;
    else if (t >= c.end) lo = mid + 1;
    else return c;
  }
  return null;
}

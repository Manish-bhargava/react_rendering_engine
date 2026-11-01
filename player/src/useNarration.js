// Minimal audio playback for one slide: base narration, interaction-layer narration,
// and the reveal cues that are synced to narration lines. Missing audio never blocks.
import { useEffect, useRef, useState, useCallback } from 'react';
import { captionFileFor, parseVtt, cueAt } from './vtt.js';

const words = (s) => s.split(/\s+/).filter(Boolean).length;

export function useNarration(vo, basePath) {
  const base = vo?.base || null;
  const baseRef = useRef(null);
  const layerRef = useRef(null);
  const wasPlaying = useRef(false);
  const [status, setStatus] = useState('none');      // none | loading | playing | paused | ended | missing | blocked
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [layer, setLayer] = useState({ id: null, status: 'none' });
  const [cues, setCues] = useState(null);            // null until a caption file is looked for
  const [layerCues, setLayerCues] = useState(null);
  const [layerTime, setLayerTime] = useState(0);
  // Volume and mute belong to the learner, not the slide: every new Audio picks them up.
  const [volume, setVolume] = useState(1);
  const [muted, setMuted] = useState(false);
  const volumeRef = useRef(1);
  const mutedRef = useRef(false);
  const applyLevel = (a) => { if (a) { a.volume = volumeRef.current; a.muted = mutedRef.current; } };

  const stopLayer = () => {
    if (layerRef.current) { layerRef.current.pause(); layerRef.current.src = ''; layerRef.current = null; }
  };

  useEffect(() => {
    setTime(0); setDuration(0); setLayer({ id: null, status: 'none' });
    if (!base?.audioFile) { setStatus('none'); return undefined; }
    const a = new Audio(basePath + base.audioFile);
    applyLevel(a);
    baseRef.current = a;
    setStatus('loading');
    a.addEventListener('error', () => setStatus('missing'));
    a.addEventListener('loadedmetadata', () => setDuration(a.duration || 0));
    a.addEventListener('timeupdate', () => setTime(a.currentTime));
    a.addEventListener('play', () => setStatus('playing'));
    a.addEventListener('pause', () => setStatus((s) => (s === 'playing' ? 'paused' : s)));
    a.addEventListener('ended', () => setStatus('ended'));
    if (vo.playback?.autoplayBase) a.play().catch(() => setStatus((s) => (s === 'missing' ? s : 'blocked')));
    return () => { a.pause(); a.src = ''; baseRef.current = null; stopLayer(); };
  }, [vo, basePath]);

  // ---- captions ----
  // Fetched rather than attached as a <track>, because the narration plays through a
  // bare Audio object. A missing file is normal and simply leaves the slide uncaptioned.
  useEffect(() => {
    setCues(null); setLayerCues(null); setLayerTime(0);
    const file = captionFileFor(base?.audioFile);
    if (!file) return undefined;
    let live = true;
    fetch(basePath + file)
      .then((r) => (r.ok ? r.text() : null))
      .then((t) => { if (live) setCues(t ? parseVtt(t) : []); })
      .catch(() => { if (live) setCues([]); });
    return () => { live = false; };
  }, [base, basePath]);

  // ---- reveal cues ----
  const cueState = useCallback(() => {
    const cues = base?.reveal?.cues || [];
    const lines = base?.lines || [];
    const counts = lines.map(words);
    const total = counts.reduce((x, y) => x + y, 0) || 1;
    const startOf = (li) => (li == null || li < 0 ? 0 : duration * counts.slice(0, li).reduce((x, y) => x + y, 0) / total);
    let prev = -1;
    const resolved = cues.map((c) => (prev = c.lineIndex ?? prev));
    const together = base?.reveal?.mode === 'together';
    return cues.map((c, i) => ({ ...c, start: startOf(together ? resolved[0] : resolved[i]) }));
  }, [base, duration]);

  const isVisible = useCallback((componentId, itemIndex) => {
    if (!['playing', 'paused', 'loading'].includes(status) || !duration) return true; // no timing -> show all
    const cue = cueState().find((c) => c.componentId === componentId && c.itemIndex === itemIndex);
    return !cue || time >= cue.start;
  }, [status, duration, time, cueState]);

  // ---- layers ----
  const openLayer = useCallback((layerId) => {
    const L = vo?.layers?.find((x) => x.layerId === layerId);
    stopLayer();
    const a = baseRef.current;
    if (a && vo.playback?.pauseBaseOnLayerOpen) {
      wasPlaying.current = wasPlaying.current || !a.paused;
      a.pause();
    }
    setLayerCues(null); setLayerTime(0);
    if (!L?.audioFile) { setLayer({ id: layerId, status: 'none' }); return; }
    const la = new Audio(basePath + L.audioFile);
    applyLevel(la);
    layerRef.current = la;
    setLayer({ id: layerId, status: 'loading' });
    la.addEventListener('error', () => setLayer({ id: layerId, status: 'missing' }));
    la.addEventListener('play', () => setLayer({ id: layerId, status: 'playing' }));
    la.addEventListener('ended', () => setLayer({ id: layerId, status: 'ended' }));
    la.addEventListener('timeupdate', () => setLayerTime(la.currentTime));
    la.play().catch(() => {});
    // the open panel's own narration carries its own captions
    const file = captionFileFor(L.audioFile);
    if (file) {
      fetch(basePath + file)
        .then((r) => (r.ok ? r.text() : null))
        .then((t) => setLayerCues(t ? parseVtt(t) : []))
        .catch(() => setLayerCues([]));
    }
  }, [vo, basePath]);

  const closeLayer = useCallback(() => {
    stopLayer();
    setLayer({ id: null, status: 'none' });
    setLayerCues(null); setLayerTime(0);
    if (vo?.playback?.resumeBaseOnLayerClose && wasPlaying.current && baseRef.current) baseRef.current.play().catch(() => {});
    wasPlaying.current = false;
  }, [vo]);

  const controls = {
    toggle: () => { const a = baseRef.current; if (!a) return; a.paused ? a.play().catch(() => {}) : a.pause(); },
    replay: () => { const a = baseRef.current; if (!a) return; a.currentTime = 0; a.play().catch(() => {}); },
    seek: (t) => { if (baseRef.current) baseRef.current.currentTime = t; },
    volume: (v) => {
      volumeRef.current = v; setVolume(v);
      // raising the slider off zero while muted brings the sound back
      if (v > 0 && mutedRef.current) { mutedRef.current = false; setMuted(false); }
      applyLevel(baseRef.current); applyLevel(layerRef.current);
    },
    toggleMute: () => {
      mutedRef.current = !mutedRef.current; setMuted(mutedRef.current);
      applyLevel(baseRef.current); applyLevel(layerRef.current);
    },
    pauseAndReset: () => { const a = baseRef.current; if (a) { a.pause(); a.currentTime = 0; } },
  };

  // While a panel is open its own narration is what is being heard, so its captions win.
  const onLayer = layer.id && layerCues && layerCues.length;
  const captions = {
    available: !!((cues && cues.length) || onLayer),
    text: (onLayer ? cueAt(layerCues, layerTime) : cueAt(cues, time))?.text || '',
  };

  return { status, time, duration, layer, volume, muted, isVisible, openLayer, closeLayer, controls, captions };
}

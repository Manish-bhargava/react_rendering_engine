import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { registry, measuredRegistry } from './registry.js';
import { tokenVars, overrideStyle } from './theme.js';
import { useNarration } from './useNarration.js';

const DATA = 'lesson/';

function useLesson() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    Promise.all(['components', 'layout', 'voiceover'].map((f) =>
      fetch(`${DATA}${f}.json`).then((r) => { if (!r.ok) throw new Error(`${f}.json: HTTP ${r.status}`); return r.json(); })))
      .then(([components, layout, voiceover]) => setData({ components, layout, voiceover }))
      .catch((e) => setError(String(e)));
  }, []);
  return { data, error };
}

function readHash() {
  const [m, s] = window.location.hash.replace('#', '').split('/');
  return { m, s };
}

export default function App() {
  const { data, error } = useLesson();
  if (error) return <div className="load-error">Could not load lesson: {error}</div>;
  if (!data) return <div className="loading">Loading lesson…</div>;
  return <Player {...data} />;
}

function Player({ components, layout, voiceover }) {
  const modules = components.modules;
  const init = readHash();
  // Each section is its own module and is launched on its own, so the module comes
  // from the URL and never changes while the player is open.
  const [mi] = useState(Math.max(0, modules.findIndex((m) => m.moduleId === init.m)));
  const mod = modules[mi];
  const [si, setSi] = useState(Math.max(0, mod.slides.findIndex((s) => s.slideId === init.s)));
  const [exited, setExited] = useState(false);
  // Captions start as components.json says and then follow the learner across slides.
  const [cc, setCc] = useState(!!mod.player?.closed_captions);
  const slide = mod.slides[si] || mod.slides[0];

  const layoutBySlide = useMemo(() => Object.fromEntries(layout.slides.map((s) => [s.slideId, s])), [layout]);
  const voBySlide = useMemo(() => Object.fromEntries(voiceover.modules.flatMap((m) => m.slides).map((s) => [s.slideId, s])), [voiceover]);
  const vo = voBySlide[slide.slideId];
  const narr = useNarration(vo, voiceover.audio.basePath);

  useEffect(() => { window.location.hash = `${mod.moduleId}/${slide.slideId}`; }, [mod, slide]);

  const goTo = (slideId) => { const i = mod.slides.findIndex((s) => s.slideId === slideId); if (i >= 0) { setSi(i); setExited(false); } };
  const nav = {
    next: () => slide.navigation.next && goTo(slide.navigation.next),
    prev: () => slide.navigation.prev && goTo(slide.navigation.prev),
    home: () => goTo(slide.navigation.home),
    exit: () => setExited(true),
  };

  // Wide screens scale the whole 1280x720 stage to fit the space actually available;
  // below the breakpoint the stage drops its frames and the slide flows in one column.
  const wrapRef = useRef(null);
  const [scale, setScale] = useState(1);
  const [stacked, setStacked] = useState(false);
  const { width: W, height: H } = layout.canvas;
  const { stackBelowPx = 900, minScale = 0.5, maxScale = 1.6 } = layout.responsive || {};
  useEffect(() => {
    const fit = () => {
      const el = wrapRef.current;
      if (!el) return;
      const availW = el.clientWidth;
      // the space left under the wrapper, measured rather than guessed
      const top = el.getBoundingClientRect().top + window.scrollY;
      const availH = Math.max(240, window.innerHeight - top - 8);
      const narrow = window.innerWidth < stackBelowPx;
      setStacked(narrow);
      if (!narrow) setScale(Math.min(Math.max(Math.min(availW / W, availH / H), minScale), maxScale));
    };
    fit();
    const ro = new ResizeObserver(fit);
    if (wrapRef.current) ro.observe(wrapRef.current);
    window.addEventListener('resize', fit);
    window.addEventListener('orientationchange', fit);
    return () => { ro.disconnect(); window.removeEventListener('resize', fit); window.removeEventListener('orientationchange', fit); };
  }, [layout, W, H, stackBelowPx, minScale, maxScale]);

  const L = layoutBySlide[slide.slideId];
  const stageRef = useRef(null);
  // content stays above the player bar (or the inferred body bottom when there is no bar)
  const floor = (layout.furniture?.playerBar?.frame?.y ?? 670) - 14;
  const fit = useContentFit(stageRef, L, !stacked, floor);
  const compById = Object.fromEntries(slide.components.map((c) => [c.id, c]));
  const bar = mod.player?.bottom_bar || {};
  const links = mod.player?.top_right_links || [];
  const bg = L.background?.color ? (L.background.color.startsWith('#') ? L.background.color : `var(--c-${L.background.color})`) : undefined;
  const furn = { ...layout.furniture, measured: !!layout.furniture?.logo };

  return (
    <div className={`app ${stacked ? 'is-flow' : 'is-stage'}`} style={tokenVars(layout.tokens)}>
      <div className="stage-wrap" ref={wrapRef} style={stacked ? {} : { height: H * scale }}>
        <div ref={stageRef} className={`stage ${stacked ? 'stacked' : ''} layout-${slide.layout}`}
          style={stacked ? { background: bg } : { width: W, height: H, transform: `scale(${scale})`, background: bg }}>
          {furn.measured ? <DeckChrome L={L} furn={furn} slide={slide} links={links} nav={nav} stacked={stacked} /> : (L.showHeaderBand && (
            <header className="header-band">
              <span className="breadcrumb">{slide.breadcrumb}</span>
              <span className="top-links">
                {links.map((l) => (
                  <button key={l.label} onClick={l.action === 'close_player' ? nav.exit : nav.home}>{l.label}</button>
                ))}
              </span>
            </header>
          ))}

          {[...L.items].sort((a, b) => a.order - b.order).map((it) => {
            const c = compById[it.componentId];
            const measured = it.source && it.source !== 'inferred';
            const Comp = (measured && measuredRegistry[c.type]) || registry[c.type];
            const f = it.frame;
            const fz = !stacked && fit[c.id];
            const style = stacked || !f ? {} : { left: f.x, top: fz ? fz.y : f.y, width: f.w, height: fz ? fz.h : f.h };
            return (
              <div key={c.id} className={`c c-${c.type} ${measured ? 'measured' : ''} ${fz?.scroll ? 'is-scroll' : ''}`} data-id={c.id}
                style={{ ...style, ...overrideStyle(it.style, layout.tokens) }}>
                {Comp ? <Comp c={c} lay={it} arrange={it.arrange} frame={stacked ? null : f} narr={narr} nav={nav} stacked={stacked} />
                  : <div className="unknown">Unknown component type: {c.type}</div>}
              </div>
            );
          })}

          {cc && narr.captions.text && (
            <div className="caption-band" aria-live="polite">
              <span>{narr.captions.text}</span>
            </div>
          )}

          {furn.measured ? <DeckPlayerBar furn={furn} slide={slide} mod={mod} narr={narr} bar={bar} nav={nav}
            stacked={stacked} cc={cc} setCc={setCc} /> : (
          <footer className="footer">
            <span className="counter">{slide.order} of {mod.slides.length}</span>
            <AudioControls narr={narr} bar={bar} />
            <span className="nav-btns">
              <button className="btn" onClick={nav.prev} disabled={!slide.navigation.prev}>‹ Prev</button>
              <button className="btn primary" onClick={nav.next} disabled={!slide.navigation.next}>Next ›</button>
            </span>
          </footer>)}

          {exited && (
            <div className="exit-scrim"><div className="exit-box">
              <p>You can now close this window.</p>
              <button className="btn" onClick={() => setExited(false)}>Back to the lesson</button>
            </div></div>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------------
// Content fit for the scaled stage. layout.json frames are planned before anything is
// rendered, so a component can need more height than its frame (a long table, many
// steps, a wrapped title). After each render this measures every component's natural
// height and returns per-component overrides { y, h, scroll }:
//   1. a component that needs more room grows; whatever sits below it in the same
//      column moves down by the same amount (a frame never shrinks);
//   2. if that would run into the player bar, the component that grew is capped and
//      scrolls inside its own frame, so nothing is clipped, hidden or overlapped.
// Frames themselves are untouched; in the single-column layout this does nothing.
const FIT_GAP = 16;            // largest gap kept between a grown component and the next one down

function useContentFit(stageRef, L, enabled, floor) {
  const [fit, setFit] = useState({});
  useLayoutEffect(() => {
    const stage = stageRef.current;
    if (!enabled || !stage) { setFit((p) => (Object.keys(p).length ? {} : p)); return undefined; }
    let raf = 0;
    const run = () => {
      raf = 0;
      // natural size of each component: the same box with its height released
      const nat = {};
      for (const el of stage.querySelectorAll(':scope > .c[data-id]')) {
        const keep = el.style.height;
        el.style.height = 'auto';
        nat[el.dataset.id] = { h: el.offsetHeight, wide: el.scrollWidth > el.clientWidth + 1 };
        el.style.height = keep;
      }
      const items = L.items.filter((it) => it.frame && nat[it.componentId])
        .map((it) => ({ id: it.componentId, f: it.frame, nat: nat[it.componentId].h, wide: nat[it.componentId].wide }))
        .sort((a, b) => a.f.y - b.f.y || a.f.x - b.f.x);
      const sameColumn = (a, b) => a.x < b.x + b.w - 1 && b.x < a.x + a.w - 1;
      const cap = {};
      let placed = [];
      for (let pass = 0; pass < 2 * items.length + 2; pass++) {
        placed = [];
        for (const it of items) {
          const h = Math.max(it.f.h, Math.min(it.nat, cap[it.id] ?? Infinity));
          let y = it.f.y; let by = null;
          for (const p of placed) {
            if (!sameColumn(p.f, it.f) || p.f.y + p.f.h > it.f.y + 1) continue;   // only what was planned above it
            const need = p.y + p.h + Math.min(FIT_GAP, it.f.y - (p.f.y + p.f.h));
            if (need > y) { y = need; by = p; }
          }
          placed.push({ ...it, y, h, by });
        }
        // the lowest component past the floor gives back the growth that pushed it there
        const worst = placed.filter((p) => p.y + p.h > floor + 0.5).sort((a, b) => b.y + b.h - (a.y + a.h))[0];
        if (!worst) break;
        let over = worst.y + worst.h - floor; let p = worst;
        while (p && over > 0.5) {
          const grown = p.h - p.f.h;
          if (grown > 0.5) { const give = Math.min(grown, over); cap[p.id] = p.h - give; over -= give; }
          p = p.by;
        }
        if (over > 0.5) break;      // the planned frames themselves run past the floor: leave them as planned
      }
      const next = {};
      for (const p of placed) {
        const scroll = p.nat > p.h + 1 || p.wide;
        if (p.y !== p.f.y || p.h !== p.f.h || scroll) next[p.id] = { y: p.y, h: p.h, scroll };
      }
      setFit((prev) => (JSON.stringify(prev) === JSON.stringify(next) ? prev : next));
    };
    const schedule = () => { if (!raf) raf = requestAnimationFrame(run); };
    run();
    document.fonts?.ready.then(schedule);
    // content that changes after load (an opened layer, a validation message) is measured again
    const mo = new MutationObserver(schedule);
    mo.observe(stage, { childList: true, subtree: true, characterData: true });
    return () => { mo.disconnect(); if (raf) cancelAnimationFrame(raf); };
  }, [stageRef, L, enabled, floor]);
  return enabled ? fit : {};
}

function AudioControls({ narr, bar }) {
  return (
    <span className="audio-ctl">
      {bar.play_pause && <button onClick={narr.controls.toggle} disabled={!['playing', 'paused', 'blocked', 'ended'].includes(narr.status)}>{narr.status === 'playing' ? 'Pause' : 'Play'}</button>}
      {bar.replay && <button onClick={narr.controls.replay} disabled={!['playing', 'paused', 'ended'].includes(narr.status)}>Replay</button>}
      {bar.seekbar && <input type="range" min="0" max={narr.duration || 0} step="0.1" value={narr.time}
        disabled={!narr.duration || bar.seekbar_readonly} onChange={(e) => narr.controls.seek(+e.target.value)} aria-label="Seek" />}
      {bar.volume && <input type="range" className="vol" min="0" max="1" step="0.05" value={narr.volume} onChange={(e) => narr.controls.volume(+e.target.value)} aria-label="Volume" />}
      {bar.fullscreen && <button onClick={() => document.documentElement.requestFullscreen?.()} aria-label="Full screen">⛶</button>}
    </span>
  );
}

const fpos = (f, stacked) => (stacked || !f ? {} : { position: 'absolute', left: f.x, top: f.y, width: f.w, height: f.h });
const shp = (s) => (s ? { background: s.fill || undefined, borderRadius: typeof s.radius === 'number' ? `${s.radius}px` : s.radius,
  border: s.border ? `${s.border.width}px solid ${s.border.color}` : undefined } : {});
const txt = (t) => (t?.style ? { fontSize: `${t.style.fontSize}px`, fontWeight: t.style.bold ? 700 : 400, color: t.style.color,
  display: 'flex', alignItems: 'center', padding: '0 10px', justifyContent: t.style.align === 'center' ? 'center' : 'flex-start' } : {});

// House chrome measured from the authored deck: header band, breadcrumb, Menu | Exit, logo; cover field and disc.
function DeckChrome({ L, furn, slide, links, nav, stacked }) {
  if (L.cover) {
    const cv = L.cover;
    return (<>
      {!stacked && cv.disc && <div className="deck-disc" style={{ ...fpos(cv.disc.frame), ...shp(cv.disc.shape) }} />}
      {cv.logoPlate && <div style={{ ...fpos(cv.logoPlate.frame, stacked), ...shp(cv.logoPlate.shape) }} />}
      {cv.logo && <img className="deck-logo" src={cv.logo.src} alt="Bodhi Learning Labs" style={fpos(cv.logo.frame, stacked)} />}
    </>);
  }
  const home = links.find((l) => l.action === 'jump_to_slide');
  const exit = links.find((l) => l.action === 'close_player');
  return (
    <header className="deck-header" style={stacked ? { background: furn.headerBand?.shape?.fill } : {}}>
      {!stacked && <div style={{ ...fpos(furn.headerBand.frame), ...shp(furn.headerBand.shape) }} />}
      <div className="deck-crumb" style={{ ...fpos(furn.breadcrumb.frame, stacked), ...txt(furn.breadcrumb) }}>{slide.breadcrumb}</div>
      <div className="deck-links" style={{ ...fpos(furn.topLinks?.frame, stacked), ...txt(furn.topLinks) }}>
        <button onClick={nav.home} title={home?.label}>Menu</button><span>|</span><button onClick={nav.exit} title={exit?.label}>Exit</button>
      </div>
      {furn.logoPlate && <div style={{ ...fpos(furn.logoPlate.frame, stacked), ...shp(furn.logoPlate.shape) }} />}
      <img className="deck-logo" src={furn.logo.src} alt="Bodhi Learning Labs" style={fpos(furn.logo.frame, stacked)} />
    </header>
  );
}

function DeckPlayerBar({ furn, slide, mod, narr, bar, nav, stacked, cc, setCc }) {
  const pct = narr.duration ? narr.time / narr.duration : 0;
  const tr = furn.progressTrack?.frame;
  // the counter and the audio group share the bar's centre line with the play and PREV / NEXT buttons
  const pb = furn.playerBar.frame;
  const mid = (h) => pb.y + (pb.h - h) / 2;
  return (
    <footer className="deck-bar" style={stacked ? { background: furn.playerBar.shape.fill } : {}}>
      {!stacked && <div style={{ ...fpos(furn.playerBar.frame), ...shp(furn.playerBar.shape) }} />}
      {furn.playButton && <button className="deck-play" aria-label={narr.status === 'playing' ? 'Pause' : 'Play'} onClick={narr.controls.toggle}
        style={{ ...fpos(furn.playButton.frame, stacked), ...shp(furn.playButton.shape) }}>{narr.status === 'playing' ? '❚❚' : '▶'}</button>}
      {tr && <DeckSeek frame={tr} shape={furn.progressTrack.shape} fill={furn.progressFill?.shape?.fill} pct={pct} narr={narr} stacked={stacked} />}
      <span className="deck-counter" style={stacked ? {} : { position: 'absolute', left: tr ? tr.x + tr.w + 14 : 300, top: mid(30), height: 30 }}>{slide.order} / {mod.slides.length}</span>
      <span className="deck-audio" style={stacked ? {} : { position: 'absolute', left: tr ? tr.x + tr.w + 80 : 380, top: mid(34), height: 34 }}>
        {bar.replay && <button onClick={narr.controls.replay} disabled={!['playing', 'paused', 'ended'].includes(narr.status)} aria-label="Replay">↺</button>}
        <span className="deck-time" aria-label="Elapsed and total time">{clock(narr.time)} / {clock(narr.duration)}</span>
        <button className={`deck-mute ${narr.muted ? 'on' : ''}`} onClick={narr.controls.toggleMute} aria-pressed={narr.muted}
          aria-label={narr.muted ? 'Unmute' : 'Mute'} title={narr.muted ? 'Unmute' : 'Mute'}>{narr.muted ? <SpeakerOff /> : <SpeakerOn />}</button>
        {bar.volume && <input type="range" className="vol" min="0" max="1" step="0.05" value={narr.volume} onChange={(e) => narr.controls.volume(+e.target.value)} aria-label="Volume" />}
        {/* no caption file for this slide leaves the button there but inert */}
        <button className={`deck-cc ${cc ? 'on' : ''}`} onClick={() => setCc(!cc)} disabled={!narr.captions.available}
          aria-pressed={cc} aria-label={cc ? 'Turn captions off' : 'Turn captions on'}
          title={narr.captions.available ? (cc ? 'Captions on' : 'Captions off') : 'No captions for this slide'}>CC</button>
        {bar.fullscreen && <button onClick={() => document.documentElement.requestFullscreen?.()} aria-label="Full screen">⛶</button>}
      </span>
      {['prevButton', 'nextButton'].map((k) => furn[k] && (
        <button key={k} className="deck-nav" disabled={k === 'prevButton' ? !slide.navigation.prev : !slide.navigation.next}
          onClick={k === 'prevButton' ? nav.prev : nav.next}
          style={{ ...fpos(furn[k].frame, stacked), ...shp(furn[k].shape), ...txt(furn[k].text), justifyContent: 'center', padding: 0 }}>{furn[k].value}</button>
      ))}
    </footer>
  );
}

// m:ss for the elapsed / total readout
const clock = (t) => {
  const s = Number.isFinite(t) && t > 0 ? Math.floor(t) : 0;
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
};

// Progress track with a drag handle. Pressing anywhere on the track seeks there, and
// dragging keeps seeking until the pointer is released (mouse, pen and touch alike).
function DeckSeek({ frame, shape, fill, pct, narr, stacked }) {
  const ref = useRef(null);
  const seekAt = (clientX) => {
    const el = ref.current;
    if (!el || !narr.duration) return;
    const r = el.getBoundingClientRect();
    narr.controls.seek(Math.min(1, Math.max(0, (clientX - r.left) / r.width)) * narr.duration);
  };
  const down = (e) => {
    if (!narr.duration) return;
    e.currentTarget.setPointerCapture?.(e.pointerId);
    seekAt(e.clientX);
  };
  const move = (e) => { if (e.currentTarget.hasPointerCapture?.(e.pointerId)) seekAt(e.clientX); };
  const key = (e) => {
    const step = { ArrowRight: 5, ArrowLeft: -5 }[e.key];
    if (step && narr.duration) { e.preventDefault(); narr.controls.seek(Math.min(narr.duration, Math.max(0, narr.time + step))); }
  };
  return (
    <div ref={ref} className="deck-track" role="slider" tabIndex={narr.duration ? 0 : -1} aria-label="Seek"
      aria-valuemin={0} aria-valuemax={Math.round(narr.duration || 0)} aria-valuenow={Math.round(narr.time || 0)}
      aria-valuetext={`${clock(narr.time)} of ${clock(narr.duration)}`}
      style={{ ...fpos(frame, stacked), ...shp(shape) }} onPointerDown={down} onPointerMove={move} onKeyDown={key}>
      <div style={{ width: `${pct * 100}%`, height: '100%', background: fill }} />
      {narr.duration > 0 && <span className="deck-thumb" style={{ left: `${pct * 100}%`, background: fill }} />}
    </div>
  );
}

const SpeakerOn = () => (
  <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2 6h2.5L8 3v10L4.5 10H2z" fill="currentColor" /><path d="M10.5 5.5a3.5 3.5 0 0 1 0 5M12.5 3.5a6.5 6.5 0 0 1 0 9" />
  </svg>
);
const SpeakerOff = () => (
  <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2 6h2.5L8 3v10L4.5 10H2z" fill="currentColor" /><path d="M10.5 6l4 4M14.5 6l-4 4" />
  </svg>
);


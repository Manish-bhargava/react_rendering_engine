// Renderers for components whose layout entry was measured from an authored deck.
// Every part carries its own absolute canvas frame; `origin` is the component frame,
// so parts are positioned relative to the component wrapper. In stacked (mobile) mode
// frames are ignored and parts flow in order.
import { useState, useMemo } from 'react';

// ---------- primitives ----------
const px = (v) => (v == null ? undefined : `${v}px`);

function posCss(frame, origin, stacked) {
  if (stacked || !frame) return {};
  const o = origin || { x: 0, y: 0 };
  return { position: 'absolute', left: frame.x - o.x, top: frame.y - o.y, width: frame.w, height: frame.h };
}

// Same frame, but free to grow downwards. Used for runs of text, where a font
// that falls back to different metrics must push the box rather than spill out of it.
function growCss(frame, origin, stacked) {
  const css = posCss(frame, origin, stacked);
  if (css.height == null) return css;
  const { height, ...rest } = css;
  return { ...rest, minHeight: height };
}

function shapeCss(shape) {
  if (!shape) return {};
  const s = {};
  if (shape.fill) s.background = shape.fill;
  if (shape.border) s.border = `${Math.max(1, shape.border.width || 1)}px solid ${shape.border.color}`;
  if (shape.radius != null) s.borderRadius = typeof shape.radius === 'number' ? px(shape.radius) : shape.radius;
  return s;
}

export function textCss(t, para) {
  if (!t) return {};
  const st = para || t.style || {};
  const s = {
    fontSize: px(st.fontSize), fontWeight: st.bold ? 700 : 400, color: st.color || undefined,
    textAlign: st.align || 'left',
  };
  return s;
}

function frameTextCss(t) {
  if (!t) return {};
  const [pt, pr, pb, pl] = t.padding || [0, 0, 0, 0];
  return {
    ...textCss(t), padding: `${pt}px ${pr}px ${pb}px ${pl}px`, display: 'flex', flexDirection: 'column',
    justifyContent: { top: 'flex-start', middle: 'center', bottom: 'flex-end' }[t.anchor] || 'flex-start',
  };
}

// A positioned box: shape (fill/border/radius) + optional text styling.
export function Box({ spec, origin, stacked, className = '', style, children, as: Tag = 'div', ...rest }) {
  if (!spec) return null;
  const t = spec.text && !spec.text.frame ? spec.text : (spec.style ? spec : null);
  return (
    <Tag className={`m-box ${className}`} {...rest}
      style={{ ...posCss(spec.frame, origin, stacked), ...shapeCss(spec.shape), ...frameTextCss(t), ...style }}>
      {children}
    </Tag>
  );
}

// A text frame whose paragraphs may each carry their own style.
function Paras({ spec, origin, stacked, lines, className = '', itemClass, offset = 0, marker }) {
  const ps = spec.paragraphStyles;
  return (
    <div className={`m-box m-text ${className}`} style={{ ...posCss(spec.frame, origin, stacked), ...frameTextCss(spec) }}>
      {lines.map((ln, i) => {
        const pre = marker === 'bullet' ? '•  ' : marker === 'number' ? `${i + 1}.  ` : '';
        return <p key={i} className={itemClass ? itemClass(i) : ''} style={textCss(spec, ps ? ps[i + offset] : null)}>{pre}{ln}</p>;
      })}
    </div>
  );
}

const visCls = (narr, c, i) => (narr.isVisible(c.id, i) ? 'item' : 'item hidden');

// ---------- text ----------
export function MText({ c, lay, stacked }) {
  return (
    <div className={`m-text role-${c.props.role || c.type}`} style={{ ...frameTextCss(lay.text), minHeight: stacked ? undefined : '100%', whiteSpace: 'pre-line' }}>
      {c.props.text}
    </div>
  );
}

// ---------- image ----------
export function MImage({ c, lay, stacked }) {
  const p = c.props; const o = lay.frame;
  return (
    <>
      <div className="m-image" style={{ ...shapeCss(lay.shape), width: '100%', height: stacked ? undefined : '100%', position: 'relative', borderStyle: p.src ? 'none' : 'dashed' }}>
        {p.src ? <img src={p.src} alt={p.alt} /> :
          lay.parts?.label && <Paras spec={lay.parts.label} origin={o} stacked={stacked} lines={['IMAGE', p.alt]} className="m-image-label" />}
      </div>
      {!p.src && lay.parts?.caption && (
        <div className="m-caption" style={{ ...posCss(lay.parts.caption.frame, o, stacked), ...frameTextCss(lay.parts.caption) }}>
          <span>search: “{p.searchTerms}”</span><span>image not yet selected</span>
        </div>
      )}
    </>
  );
}

// ---------- callout ----------
export function MCallout({ c, lay, stacked }) {
  const o = lay.frame; const tag = lay.parts?.tag;
  return (
    <div className={`m-callout ${c.props.kind}`} style={{ ...shapeCss(lay.shape), width: '100%', height: stacked ? 'auto' : '100%', position: 'relative' }}>
      {tag && <Box spec={tag} origin={o} stacked={stacked}>{tag.value}</Box>}
      <Box spec={lay.parts.body} origin={o} stacked={stacked}>{c.props.text}</Box>
    </div>
  );
}

// ---------- chips with bodies (cardGrid, comparison) ----------
export function MCards({ c, lay, narr, stacked }) {
  const list = c.props.cards || c.props.columns; const o = lay.frame;
  return list.map((k, i) => {
    const it = lay.items[i] || {};
    return (
      <div key={i} className={`${visCls(narr, c, i)} m-group`}>
        {it.panel && <Box spec={it.panel} origin={o} stacked={stacked} className="m-panel" />}
        {it.header && <Box spec={it.header} origin={o} stacked={stacked} className="m-chip">{k.title}</Box>}
        {it.body && <Box spec={it.body} origin={o} stacked={stacked} style={{ whiteSpace: 'pre-line' }}>{k.body}</Box>}
      </div>
    );
  });
}

// ---------- icons ----------
export function MIcons({ c, lay, narr, stacked }) {
  const o = lay.frame;
  const menu = c.props.interaction?.type === 'menu' ? c.props.interaction : null;
  const [visited, setVisited] = useState({});
  const [msg, setMsg] = useState('');
  return (
    <>
      {c.props.items.map((it, i) => {
        const m = lay.items[i];
        if (!m) return null;
        const hit = m.icon ? {
          x: Math.min(m.icon.frame.x, m.label.frame.x), y: m.icon.frame.y,
          w: Math.max(m.label.frame.w, m.icon.frame.w), h: m.label.frame.y + m.label.frame.h - m.icon.frame.y,
        } : m.label.frame;
        const Tag = menu ? 'button' : 'div';
        return (
          <Tag key={i} type={menu ? 'button' : undefined}
            className={`${visCls(narr, c, i)} m-icon-item ${menu ? 'hotspot' : ''} ${visited[i] ? 'visited' : ''}`}
            style={posCss(hit, o, stacked)}
            onClick={menu ? () => { setVisited({ ...visited, [i]: true }); setMsg(menu.targets[i] ? '' : `“${it.label}”: the source does not name a target slide for this topic yet.`); } : undefined}>
            {m.icon?.src
              ? <img src={m.icon.src} alt="" style={posCss(m.icon.frame, hit, stacked)} />
              : <span className="m-icon-missing" style={posCss(m.icon?.frame, hit, stacked)} title={it.icon.name} />}
            <span className="m-icon-label" style={{ ...posCss(m.label.frame, hit, stacked), ...frameTextCss(m.label) }}>{it.label}</span>
          </Tag>
        );
      })}
      {msg && <p className="menu-msg" style={stacked ? {} : { position: 'absolute', left: 0, bottom: -30 }}>{msg}</p>}
    </>
  );
}

// ---------- paragraph lists ----------
export function MList({ c, lay, narr, nav, stacked }) {
  const p = c.props;
  let lines, offset = 0;
  if (c.type === 'definition') {
    lines = p.terms.flatMap((d) => [d.term, d.description]);
    return (
      <div className="m-box m-text" style={{ ...growCss(lay.frame, lay.frame, stacked), ...frameTextCss(lay.text) }}>
        {p.terms.map((d, i) => (
          <div key={i} className={visCls(narr, c, i)}>
            <p style={textCss(lay.text, lay.text.paragraphStyles?.[i * 2])}>{d.term}</p>
            <p style={{ ...textCss(lay.text, lay.text.paragraphStyles?.[i * 2 + 1]), whiteSpace: 'pre-line' }}>{d.description}</p>
          </div>
        ))}
      </div>
    );
  }
  if (c.type === 'objectivesList') { lines = p.items.map((o) => o.text); if (p.intro) offset = 1; }
  else if (c.type === 'summary') lines = p.points;
  else if (c.type === 'results') lines = p.lines;
  else lines = p.items;
  const spec = { ...lay.text, frame: lay.frame };
  return (
    <div className="m-list" style={{ height: '100%' }}>
      <div className="m-box m-text" style={{ ...growCss(lay.frame, lay.frame, stacked), ...frameTextCss(spec) }}>
        {p.intro && <p style={textCss(spec, spec.paragraphStyles?.[0])}>{p.intro}</p>}
        {lines.map((ln, i) => {
          const pre = lay.marker === 'bullet' ? '•  ' : lay.marker === 'number' ? `${i + 1}.  ` : '';
          return <p key={i} className={visCls(narr, c, i)} style={textCss(spec, spec.paragraphStyles?.[i + offset])}>{pre}{ln}</p>;
        })}
      </div>
      {c.type === 'results' && <ResultsActions c={c} nav={nav} />}
    </div>
  );
}

function ResultsActions({ c, nav }) {
  if (!nav) return null;
  return (
    <div className="m-results-actions">
      {c.props.actions.includes('review') && <button className="m-pill" onClick={nav.home}>Review section</button>}
      {c.props.actions.includes('close') && <button className="m-pill" onClick={nav.exit}>Close</button>}
    </div>
  );
}

// ---------- table ----------
export function MTable({ c, lay, narr, stacked }) {
  const t = lay.table;
  // Cell inset comes from the layout so the deck and the player agree.
  const [pt, pr, pb, pl] = t.cellPadding || [8, 16, 8, 16];
  const cell = { padding: `${pt}px ${pr}px ${pb}px ${pl}px` };
  const total = t.colWidths.reduce((a, b) => a + b, 0) || 1;
  return (
    <div className="m-table-wrap">
      <table className="m-table" style={{ width: '100%', minWidth: stacked ? Math.min(total, 560) : undefined }}>
        {/* percentages so the column balance survives any width */}
        <colgroup>{t.colWidths.map((w, i) => <col key={i} style={{ width: `${(w / total) * 100}%` }} />)}</colgroup>
        <thead>
          <tr className={visCls(narr, c, 0)} style={{ height: stacked ? undefined : px(t.rowHeights[0]), background: t.header.fill }}>
            {c.props.headers.map((h, i) => <th key={i} style={{ ...textCss({ style: t.header.style }), ...cell }}>{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {c.props.rows.map((r, ri) => {
            const rs = t.rows[ri] || t.rows[t.rows.length - 1];
            return (
              <tr key={ri} className={visCls(narr, c, ri + 1)} style={{ height: stacked ? undefined : px(t.rowHeights[ri + 1]), background: rs.fill }}>
                {r.map((v, ci) => <td key={ci} style={{ ...textCss({ style: ci === 0 ? rs.firstColStyle : rs.style }), ...cell }}>{v}</td>)}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------- process (+ interaction layers) ----------
export function MProcess({ c, lay, narr, stacked }) {
  const o = lay.frame; const ix = c.props.interaction;
  const layered = ix?.type === 'layers';
  const [visited, setVisited] = useState({});
  const open = layered ? ix.layers.find((L) => L.layerId === narr.layer.id) : null;
  const ls = lay.parts?.layerStyle;
  return (
    <>
      {lay.parts?.rail && <Box spec={lay.parts.rail} origin={o} stacked={stacked} className="m-rail" />}
      {c.props.steps.map((s, i) => {
        const it = lay.items[i] || {};
        const L = layered ? ix.layers.find((x) => x.stepIndex === i) : null;
        const click = L ? () => { setVisited({ ...visited, [L.layerId]: true }); narr.openLayer(L.layerId); } : undefined;
        const state = L ? `${open?.layerId === L.layerId ? 'active' : ''} ${visited[L.layerId] ? 'visited' : ''}` : '';
        return (
          <div key={i} className={`${visCls(narr, c, i)} m-step ${L ? 'clickable' : ''} ${state}`}>
            {it.badge && <Box spec={it.badge} origin={o} stacked={stacked} as={L ? 'button' : 'div'} onClick={click} className="m-badge" aria-label={L ? `Open ${s.label}` : undefined}>{i + 1}</Box>}
            {it.label && <Box spec={it.label} origin={o} stacked={stacked} as={L ? 'button' : 'div'} onClick={click} className="m-step-label">{s.label}</Box>}
          </div>
        );
      })}
      {layered && lay.parts?.layerPanel && (
        <div className="m-layer-panel" style={posCss(lay.parts.layerPanel.frame, o, stacked)} aria-live="polite">
          {open ? (
            <div className="m-layer">
              <div className="m-layer-head">
                <div className="m-chip" style={{ ...shapeCss(ls?.header.shape), ...frameTextCss(ls?.header.text),
                  width: stacked ? undefined : ls?.header.frame.w, minHeight: ls?.header.frame.h }}>{open.label}</div>
                <button type="button" className="m-close" onClick={narr.closeLayer} aria-label="Close">×</button>
              </div>
              {open.lines.map((t, i) => <p key={i} style={textCss(ls?.body)}>{t}</p>)}
              {narr.layer.status === 'missing' && <p className="audio-note">Layer audio not supplied.</p>}
            </div>
          ) : <p className="m-layer-empty">{ix.instruction}</p>}
        </div>
      )}
    </>
  );
}

// ---------- knowledge checks ----------
function useAttempts(c, narr, nav) {
  const [tries, setTries] = useState(0);
  const [shown, setShown] = useState(null);
  const [invalid, setInvalid] = useState(false);
  const layer = (k) => c.props.feedback.find((f) => f.kind === k);
  const submit = (has, ok) => {
    if (!has) { setInvalid(true); return; }
    setInvalid(false); narr.controls.pauseAndReset();
    const n = tries + 1; setTries(n);
    setShown(ok ? layer('correct') : n < (c.props.attempts || 1) ? layer('try_again') : layer('incorrect'));
  };
  const run = (actions, reset) => {
    if (actions.includes('hide_layer')) setShown(null);
    if (actions.includes('jump_to_next_slide')) nav.next(); else reset?.();
  };
  return { shown, invalid, submit, run, done: shown && shown.kind !== 'try_again' };
}

function Verdicts({ c, lay, q, stacked, reset }) {
  const o = lay.frame; const P = lay.parts; const f = q.shown;
  if (!f) return q.invalid ? <p className="invalid" style={posCss(P.verdictCorrect?.frame, o, stacked)}>Please select an answer before you submit.</p> : null;
  const ok = f.kind === 'correct';
  const strip = ok ? P.verdictCorrect : P.verdictIncorrect;
  const final = f.kind === 'incorrect';
  const answer = c.type === 'multipleChoice' ? `The correct answer is ${c.props.correctKeys.join(', ')}.` : 'The correct order is shown.';
  return (
    <>
      {strip && <Box spec={strip} origin={o} stacked={stacked} className="m-verdict" style={{ ...frameTextCss(strip.text), padding: '0 14px', justifyContent: 'center' }}>
        {f.heading}{f.kind === 'try_again' ? ` ${f.body}` : final ? ` ${answer}` : ''}
      </Box>}
      {f.kind !== 'try_again' && P.rationale && <Box spec={P.rationale} origin={o} stacked={stacked} className="m-rationale" style={frameTextCss(P.rationale.text)}>{f.body}</Box>}
      <button className="m-pill m-feedback-btn" style={stacked || !P.rationale ? {} : { position: 'absolute', right: o.x + o.w - (P.rationale.frame.x + P.rationale.frame.w), top: P.rationale.frame.y + P.rationale.frame.h - o.y + 8 }}
        onClick={() => q.run(f.onClick, reset)}>{f.button}</button>
    </>
  );
}

export function MMultipleChoice({ c, lay, narr, nav, stacked }) {
  const p = c.props; const o = lay.frame; const P = lay.parts;
  const [sel, setSel] = useState(null);
  const q = useAttempts(c, narr, nav);
  const optStyle = P.options;
  const shownCorrect = q.shown?.kind === 'incorrect' || q.shown?.kind === 'correct';
  return (
    <>
      {P.typeBadge && <Box spec={P.typeBadge} origin={o} stacked={stacked}>{p.questionType}</Box>}
      {P.stem && <Box spec={P.stem} origin={o} stacked={stacked}>{p.stem}</Box>}
      {optStyle && (
        <div className="m-options" style={{ ...posCss(optStyle.frame, o, stacked), ...frameTextCss(optStyle) }}>
          {/* the list is its own box so every option row can share one height */}
          <div className="m-option-list" role="radiogroup">
            {p.options.map((op) => (
              <label key={op.key} className={`m-option ${sel === op.key ? 'selected' : ''} ${shownCorrect && op.correct ? 'is-correct' : ''}`}>
                <input type="radio" name={c.id} checked={sel === op.key} disabled={!!q.done} onChange={() => setSel(op.key)} />
                <span className="m-key">{op.key}.</span><span>{op.text}</span>
              </label>
            ))}
          </div>
          <button className="m-pill m-submit" disabled={!!q.done} onClick={() => q.submit(sel != null, p.correctKeys.includes(sel))}>Submit</button>
        </div>
      )}
      <Verdicts c={c} lay={lay} q={q} stacked={stacked} reset={() => setSel(null)} />
    </>
  );
}

function startOrder(items) {
  const n = items.length;
  const step = n % 2 === 1 ? 2 : (n % 3 === 0 ? n - 1 : 3);
  const idx = items.map((_, i) => (i * step + 1) % n);
  return (new Set(idx).size === n ? idx : items.map((_, i) => n - 1 - i)).map((i) => items[i]);
}

export function MSequence({ c, lay, narr, nav, stacked }) {
  const o = lay.frame; const P = lay.parts;
  const initial = useMemo(() => startOrder(c.props.items), [c]);
  const [list, setList] = useState(initial);
  const [pick, setPick] = useState(null);
  const q = useAttempts(c, narr, nav);
  const swap = (a, b) => { if (a == null || b == null || a === b) return; const n = [...list]; [n[a], n[b]] = [n[b], n[a]]; setList(n); };
  const solved = q.shown?.kind === 'incorrect';
  const shown = solved ? [...c.props.items].sort((a, b) => a.correctPosition - b.correctPosition) : list;
  const correct = list.every((it, i) => it.correctPosition === i + 1);
  const last = lay.slots.filter(Boolean).slice(-1)[0];
  return (
    <>
      {P.typeBadge && <Box spec={P.typeBadge} origin={o} stacked={stacked}>{c.props.questionType}</Box>}
      {/* the slots sit in their own box so they can share one height when they wrap */}
      <div className="m-seq-list">
        {shown.map((it, i) => {
          const slot = lay.slots[i];
          return (
            <Box key={it.id} spec={slot} origin={o} stacked={stacked} as="button" draggable={!q.done}
              className={`m-seq ${pick === i ? 'picked' : ''}`}
              onClick={() => { if (q.done) return; if (pick == null) setPick(i); else { swap(pick, i); setPick(null); } }}
              onDragStart={(e) => { e.dataTransfer.setData('text/plain', String(i)); }}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => { e.preventDefault(); swap(+e.dataTransfer.getData('text/plain'), i); setPick(null); }}>
              <span className="m-seq-num">{i + 1}</span>{it.label}
            </Box>
          );
        })}
      </div>
      {last && <button className="m-pill m-submit" disabled={!!q.done}
        style={stacked ? {} : { position: 'absolute', left: last.frame.x + last.frame.w - o.x + 24, top: last.frame.y - o.y + 10 }}
        onClick={() => q.submit(true, correct)}>Submit</button>}
      <Verdicts c={c} lay={lay} q={q} stacked={stacked} reset={() => setList(initial)} />
    </>
  );
}

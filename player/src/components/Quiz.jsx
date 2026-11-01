import { useState, useMemo } from 'react';
import { createPortal } from 'react-dom';

// Shared attempt logic: correct -> "correct" layer; wrong -> "try_again" until the
// last attempt, then "incorrect". Layer buttons run the source on_click actions.
function useAttempts(c, narr, nav) {
  const [tries, setTries] = useState(0);
  const [shown, setShown] = useState(null);
  const [invalid, setInvalid] = useState(false);
  const layer = (kind) => c.props.feedback.find((f) => f.kind === kind);
  const submit = (hasAnswer, isCorrect) => {
    if (!hasAnswer) { setInvalid(true); return; }
    setInvalid(false);
    narr.controls.pauseAndReset();                    // voiceover playback.onSubmit
    const n = tries + 1;
    setTries(n);
    setShown(isCorrect ? layer('correct') : n < (c.props.attempts || 1) ? layer('try_again') : layer('incorrect'));
  };
  const run = (actions, reset) => {
    if (actions.includes('hide_layer')) setShown(null);
    if (actions.includes('jump_to_next_slide')) nav.next();
    else reset?.();
  };
  return { shown, invalid, submit, run, done: shown && shown.kind !== 'try_again' };
}

function Feedback({ f, frame, overlay, onAction }) {
  if (!f) return null;
  const o = overlay?.frame;
  // the scrim is rendered into the stage itself, so it covers the whole slide even when
  // the quiz box scrolls; the overlay frame is in stage coordinates and is used as-is
  const style = o ? { left: o.x, top: o.y, width: o.w, maxHeight: o.h } : {};
  const stage = typeof document !== 'undefined' && document.querySelector('.stage');
  const scrim = (
    <div className="feedback-scrim">
      <div className={`feedback ${f.kind}`} role="dialog" aria-label={f.heading} style={style}>
        <h3>{f.heading}</h3>
        <p>{f.body}</p>
        <button className="btn primary" onClick={() => onAction(f.onClick)}>{f.button}</button>
      </div>
    </div>
  );
  return stage ? createPortal(scrim, stage) : scrim;
}

export function MultipleChoice({ c, arrange, frame, narr, nav }) {
  const [sel, setSel] = useState(null);
  const q = useAttempts(c, narr, nav);
  const p = c.props;
  return (
    <div className="quiz">
      <p className="stem">{p.stem}</p>
      <div className="options" role="radiogroup">
        {p.options.map((o) => (
          <label key={o.key} className={`option ${sel === o.key ? 'selected' : ''}`}>
            <input type="radio" name={c.id} checked={sel === o.key} disabled={!!q.done}
              onChange={() => setSel(o.key)} />
            <span className="key">{o.key}</span><span>{o.text}</span>
          </label>
        ))}
      </div>
      {q.invalid && <p className="invalid">Please select an answer before you submit.</p>}
      <button className="btn primary submit" disabled={!!q.done}
        onClick={() => q.submit(sel != null, p.correctKeys.includes(sel))}>Submit</button>
      <Feedback f={q.shown} frame={frame} overlay={arrange?.feedbackOverlay}
        onAction={(a) => q.run(a, () => setSel(null))} />
    </div>
  );
}

export function TrueFalse({ c, arrange, frame, narr, nav }) {
  const [sel, setSel] = useState(null);
  const q = useAttempts(c, narr, nav);
  const p = c.props;
  return (
    <div className="quiz true-false">
      <p className="stem">{p.stem}</p>
      <div className="options" role="radiogroup">
        {p.options.map((o) => (
          <label key={o.key} className={`option ${sel === o.key ? 'selected' : ''}`}>
            <input type="radio" name={c.id} checked={sel === o.key} disabled={!!q.done}
              onChange={() => setSel(o.key)} />
            <span className="key">{o.key}</span><span>{o.text}</span>
          </label>
        ))}
      </div>
      {q.invalid && <p className="invalid">Please select an answer before you submit.</p>}
      {!q.done && (
        <button className="btn primary submit"
          onClick={() => q.submit(sel != null, p.correctKeys.includes(sel))}>Submit</button>
      )}
      {q.done && p.rationale && <div className="rationale"><strong>Explanation:</strong> {p.rationale}</div>}
      <Feedback f={q.shown} frame={frame} overlay={arrange?.feedbackOverlay}
        onAction={(a) => q.run(a, () => setSel(null))} />
    </div>
  );
}

export function MultiSelect({ c, arrange, frame, narr, nav }) {
  const [sel, setSel] = useState([]);
  const q = useAttempts(c, narr, nav);
  const p = c.props;
  const toggle = (key) => {
    setSel((prev) => prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]);
  };
  const isCorrect = () => {
    const correct = new Set(p.correctKeys);
    const selected = new Set(sel);
    return correct.size === selected.size && [...correct].every((k) => selected.has(k));
  };
  return (
    <div className="quiz multi-select">
      <p className="stem">{p.stem}</p>
      <p className="hint">Select all that apply.</p>
      <div className="options" role="group">
        {p.options.map((o) => (
          <label key={o.key} className={`option ${sel.includes(o.key) ? 'selected' : ''}`}>
            <input type="checkbox" checked={sel.includes(o.key)} disabled={!!q.done}
              onChange={() => toggle(o.key)} />
            <span className="key">{o.key}</span><span>{o.text}</span>
          </label>
        ))}
      </div>
      {q.invalid && <p className="invalid">Please select at least one answer before you submit.</p>}
      {!q.done && (
        <button className="btn primary submit"
          onClick={() => q.submit(sel.length > 0, isCorrect())}>Submit</button>
      )}
      {q.done && p.rationale && <div className="rationale"><strong>Explanation:</strong> {p.rationale}</div>}
      <Feedback f={q.shown} frame={frame} overlay={arrange?.feedbackOverlay}
        onAction={(a) => q.run(a, () => setSel([]))} />
    </div>
  );
}

// Deterministic start order that is never already correct.
function startOrder(items) {
  const n = items.length;
  const step = n % 2 === 1 ? 2 : (n % 3 === 0 ? n - 1 : 3);
  const idx = items.map((_, i) => (i * step + 1) % n);
  const order = new Set(idx).size === n ? idx : items.map((_, i) => n - 1 - i);
  return order.map((i) => items[i]);
}

// Matching (drag-and-drop): learner pairs each label with the correct match text.
// The items start shuffled on the right side; the learner drags them next to labels.
export function Matching({ c, arrange, frame, narr, nav }) {
  const p = c.props;
  const initial = useMemo(() => {
    // Shuffle matchTexts so the learner has to rearrange
    const texts = p.items.map((it) => it.matchText);
    const shuffled = [...texts];
    // Simple deterministic shuffle that never starts correct
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = (i * 7 + 3) % (i + 1);
      [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }
    // If still in order, reverse
    if (shuffled.every((t, i) => t === texts[i])) shuffled.reverse();
    return shuffled;
  }, [p.items]);

  const [answers, setAnswers] = useState(initial);
  const [drag, setDrag] = useState(null);
  const q = useAttempts(c, narr, nav);

  const swap = (from, to) => {
    if (from === to) return;
    const next = [...answers];
    [next[from], next[to]] = [next[to], next[from]];
    setAnswers(next);
  };

  const correct = p.items.every((it, i) => answers[i] === it.matchText);

  return (
    <div className="quiz matching">
      {p.stem && <p className="stem">{p.stem}</p>}
      <div className="match-grid">
        {p.items.map((it, i) => (
          <div key={it.id} className="match-row">
            <span className="match-label">{it.label}</span>
            <span className="match-arrow" aria-hidden="true">→</span>
            <span className={`match-answer ${drag === i ? 'dragging' : ''}`}
              draggable={!q.done}
              onDragStart={() => setDrag(i)}
              onDragOver={(e) => e.preventDefault()}
              onDrop={() => { swap(drag, i); setDrag(null); }}
              onDragEnd={() => setDrag(null)}>
              {answers[i]}
            </span>
          </div>
        ))}
      </div>
      {q.invalid && <p className="invalid">{p.onSubmitWithNoSelection || 'Please match all items before you submit.'}</p>}
      <button className="btn primary submit" disabled={!!q.done}
        onClick={() => q.submit(true, correct)}>Submit</button>
      <Feedback f={q.shown} frame={frame} overlay={arrange?.feedbackOverlay}
        onAction={(a) => q.run(a, () => setAnswers(initial))} />
    </div>
  );
}

export function Sequence({ c, arrange, frame, narr, nav }) {
  const initial = useMemo(() => startOrder(c.props.items), [c]);
  const [list, setList] = useState(initial);
  const [drag, setDrag] = useState(null);
  const q = useAttempts(c, narr, nav);
  const move = (from, to) => {
    if (to < 0 || to >= list.length || from === to) return;
    const next = [...list]; const [x] = next.splice(from, 1); next.splice(to, 0, x); setList(next);
  };
  const correct = list.every((it, i) => it.correctPosition === i + 1);
  return (
    <div className="quiz">
      {c.props.stem && <p className="stem">{c.props.stem}</p>}
      <ol className="seq-list">
        {list.map((it, i) => (
          <li key={it.id} draggable={!q.done} className={`seq-item ${drag === i ? 'dragging' : ''}`}
            onDragStart={() => setDrag(i)} onDragOver={(e) => e.preventDefault()}
            onDrop={() => { move(drag, i); setDrag(null); }} onDragEnd={() => setDrag(null)}>
            <span className="grip" aria-hidden="true">⋮⋮</span>
            <span className="seq-label">{it.label}</span>
            <span className="seq-btns">
              <button type="button" aria-label="Move up" disabled={!!q.done || i === 0} onClick={() => move(i, i - 1)}>▲</button>
              <button type="button" aria-label="Move down" disabled={!!q.done || i === list.length - 1} onClick={() => move(i, i + 1)}>▼</button>
            </span>
          </li>
        ))}
      </ol>
      <button className="btn primary submit" disabled={!!q.done} onClick={() => q.submit(true, correct)}>Submit</button>
      <Feedback f={q.shown} frame={frame} overlay={arrange?.feedbackOverlay}
        onAction={(a) => q.run(a, () => setList(initial))} />
    </div>
  );
}

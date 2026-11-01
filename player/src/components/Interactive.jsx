import { useState } from 'react';
import { arrangeStyle } from '../theme.js';

// Process: a plain numbered track, or (when props.interaction.type === 'layers')
// a stage list whose items open interaction layers with their own narration.
export function Process({ c, arrange, narr }) {
  const ix = c.props.interaction;
  const [visited, setVisited] = useState({});
  const vis = (i) => (narr.isVisible(c.id, i) ? 'item' : 'item hidden');

  if (!ix || ix.type !== 'layers') {
    return (
      <ol className="process-track" style={arrangeStyle(arrange)}>
        {c.props.steps.map((s, i) => (
          <li key={i} className={`${vis(i)} step`}>
            <span className="badge">{i + 1}</span>
            <span className="step-label">{s.label}</span>
          </li>
        ))}
      </ol>
    );
  }

  const open = ix.layers.find((L) => L.layerId === narr.layer.id);
  const openLayer = (L) => { setVisited({ ...visited, [L.layerId]: true }); narr.openLayer(L.layerId); };

  return (
    <div className="process-layers" style={arrangeStyle(arrange)}>
      <ol className="stage-tabs">
        {c.props.steps.map((s, i) => {
          const L = ix.layers.find((x) => x.stepIndex === i);
          const active = open && L && open.layerId === L.layerId;
          return (
            <li key={i} className={vis(i)}>
              <button type="button" className={`stage-tab ${active ? 'active' : ''} ${L && visited[L.layerId] ? 'visited' : ''}`}
                onClick={() => L && openLayer(L)} aria-expanded={!!active}>
                <span className="badge">{i + 1}</span>{s.label}
              </button>
            </li>
          );
        })}
      </ol>
      <div className="layer-panel" aria-live="polite">
        {open ? (
          <>
            <div className="layer-head">
              <h3>{open.label}</h3>
              <button type="button" className="close" onClick={narr.closeLayer} aria-label="Close">×</button>
            </div>
            {open.lines.map((t, i) => <p key={i}>{t}</p>)}
            {narr.layer.status === 'missing' && <p className="audio-note">Layer audio not available.</p>}
          </>
        ) : (
          <p className="layer-empty">{ix.instruction}</p>
        )}
      </div>
    </div>
  );
}

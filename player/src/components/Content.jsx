import { useState } from 'react';
import { arrangeStyle } from '../theme.js';

const vis = (narr, c, i) => (narr.isVisible(c.id, i) ? 'item' : 'item hidden');
const pre = (t) => <span className="pre">{t}</span>;

export function Image({ c }) {
  const p = c.props;
  if (p.src) return <img className="image" src={p.src} alt={p.alt} />;
  // house placeholder: a tinted panel naming the picture, with the search note under it
  return (
    <figure className="image-slot" role="img" aria-label={p.alt}>
      <div className="image unresolved">
        <div className="unresolved-tag">Image</div>
        <div className="unresolved-alt">{p.alt}</div>
      </div>
      <figcaption className="unresolved-meta">
        <span>search: “{p.searchTerms}”</span><span>image not yet selected</span>
      </figcaption>
    </figure>
  );
}

export function Callout({ c }) {
  const label = { warning: 'Important', note: 'Note', tip: 'Tip' }[c.props.kind] || c.props.kind;
  return (
    <aside className={`callout ${c.props.kind}`}>
      <strong>{label}</strong>
      <span>{c.props.text}</span>
    </aside>
  );
}

export function BulletList({ c, arrange, narr }) {
  return (
    <ul className={`bullets ${c.props.style || ''}`} style={arrangeStyle(arrange)}>
      {c.props.items.map((t, i) => <li key={i} className={vis(narr, c, i)}>{t}</li>)}
    </ul>
  );
}

export function ObjectivesList({ c, arrange, narr }) {
  return (
    <ol className="objectives" style={arrangeStyle(arrange)}>
      {c.props.items.map((o, i) => (
        <li key={o.id} className={vis(narr, c, i)}><span className="num">{i + 1}</span>{o.text}</li>
      ))}
    </ol>
  );
}

export function IconGrid({ c, arrange, narr }) {
  const menu = c.props.interaction?.type === 'menu' ? c.props.interaction : null;
  const [visited, setVisited] = useState({});
  const [msg, setMsg] = useState('');
  const Item = menu ? 'button' : 'div';
  return (
    <div className="icon-grid-wrap">
      <div className="icon-grid" style={arrangeStyle(arrange)}>
        {c.props.items.map((it, i) => (
          <Item key={i} type={menu ? 'button' : undefined}
            className={`${vis(narr, c, i)} icon-item ${menu ? 'hotspot' : ''} ${visited[i] ? 'visited' : ''}`}
            onClick={menu ? () => { setVisited({ ...visited, [i]: true }); setMsg(menu.targets[i] ? '' : `“${it.label}”: the source does not name a target slide for this topic yet.`); } : undefined}>
            <span className="icon" title={`icon: ${it.icon.name} (${it.icon.assetStatus})`} aria-hidden="true" />
            <span className="icon-label">{it.label}</span>
          </Item>
        ))}
      </div>
      {msg && <p className="menu-msg">{msg}</p>}
    </div>
  );
}

export function CardGrid({ c, arrange, narr }) {
  return (
    <div className="card-grid" style={arrangeStyle(arrange)}>
      {c.props.cards.map((k, i) => (
        <article key={i} className={`${vis(narr, c, i)} card`}>
          <h3>{k.title}</h3>
          {k.body && <p>{pre(k.body)}</p>}
        </article>
      ))}
    </div>
  );
}

export function Definition({ c, arrange, narr }) {
  return (
    <dl className="definition" style={arrangeStyle(arrange)}>
      {c.props.terms.map((d, i) => (
        <div key={i} className={`${vis(narr, c, i)} def ${i === 0 ? 'primary' : ''}`}>
          <dt>{d.term}</dt>
          <dd>{pre(d.description)}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Comparison({ c, arrange, narr }) {
  return (
    <div className="comparison" style={arrangeStyle(arrange)}>
      {c.props.columns.map((col, i) => (
        <section key={i} className={`${vis(narr, c, i)} compare-col`}>
          <h3>{col.title}</h3>
          <p>{pre(col.body)}</p>
          {i < c.props.columns.length - 1 && <span className="vs" aria-hidden="true">vs</span>}
        </section>
      ))}
    </div>
  );
}

export function DataTable({ c, arrange, narr }) {
  const cols = arrange?.columnTemplate?.split(' ');
  return (
    <table className="data-table">
      {cols && <colgroup>{cols.map((w, i) => <col key={i} style={{ width: `${(parseFloat(w) / cols.reduce((a, x) => a + parseFloat(x), 0)) * 100}%` }} />)}</colgroup>}
      <thead><tr className={vis(narr, c, 0)}>{c.props.headers.map((h, i) => <th key={i}>{h}</th>)}</tr></thead>
      <tbody>
        {c.props.rows.map((r, ri) => (
          <tr key={ri} className={vis(narr, c, ri + 1)}>{r.map((cell, ci) => <td key={ci}>{cell}</td>)}</tr>
        ))}
      </tbody>
    </table>
  );
}

export function Summary({ c, arrange, narr }) {
  return (
    <ul className="summary" style={arrangeStyle(arrange)}>
      {c.props.points.map((t, i) => <li key={i} className={vis(narr, c, i)}>{t}</li>)}
    </ul>
  );
}

export function References({ c, arrange, narr }) {
  return (
    <ol className="references" style={arrangeStyle(arrange)}>
      {c.props.items.map((t, i) => <li key={i} className={vis(narr, c, i)}>{t}</li>)}
    </ol>
  );
}

export function Results({ c, arrange, nav }) {
  return (
    <div className="results" style={arrangeStyle(arrange)}>
      {c.props.lines.map((t, i) => <p key={i}>{t}</p>)}
      <div className="results-actions">
        {c.props.actions.includes('review') && <button className="btn" onClick={nav.home}>Review section</button>}
        {c.props.actions.includes('close') && <button className="btn primary" onClick={nav.exit}>Close</button>}
      </div>
    </div>
  );
}

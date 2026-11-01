// Turns layout.json design tokens into CSS variables, and token names into CSS values.

export function tokenVars(tokens) {
  const v = {};
  for (const [k, c] of Object.entries(tokens.colors)) v[`--c-${k}`] = c;
  for (const [k, s] of Object.entries(tokens.font.sizes)) v[`--fs-${k}`] = `${s}px`;
  for (const [k, s] of Object.entries(tokens.spacing)) v[`--sp-${k}`] = `${s}px`;
  for (const [k, s] of Object.entries(tokens.radius)) v[`--r-${k}`] = `${s}px`;
  for (const [k, s] of Object.entries(tokens.shadows)) v[`--sh-${k}`] = s;
  v['--font'] = tokens.font.family;
  v['--lh'] = tokens.font.lineHeight;
  return v;
}

// Only the overrides a slide entry may carry; everything else is in styles.css.
export function overrideStyle(style = {}, tokens) {
  const out = {};
  if (style.fontSize) out.fontSize = tokens.font.sizes[style.fontSize] ? `var(--fs-${style.fontSize})` : style.fontSize;
  if (style.color) out.color = tokens.colors[style.color] ? `var(--c-${style.color})` : style.color;
  if (style.radius) out['--item-radius'] = `var(--r-${style.radius})`;
  return out;
}

export function arrangeStyle(arrange) {
  if (!arrange) return {};
  const s = {};
  if (arrange.display === 'grid') {
    s.display = 'grid';
    s.gridTemplateColumns = typeof arrange.columns === 'number' ? `repeat(${arrange.columns}, minmax(0, 1fr))` : arrange.columns;
    s.gap = `${arrange.gap ?? 16}px`;
    if (arrange.alignContent) s.alignContent = arrange.alignContent;
  } else if (arrange.display === 'flex') {
    s.display = 'flex';
    s.flexDirection = arrange.direction || 'row';
    s.gap = `${arrange.gap ?? 16}px`;
    if (arrange.justify) s.justifyContent = arrange.justify === 'start' ? 'flex-start' : arrange.justify;
    if (arrange.align) s.alignItems = arrange.align;
  }
  return s;
}

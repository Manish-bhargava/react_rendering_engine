export function Heading({ c }) {
  const Tag = `h${Math.min(c.props.level || 1, 3)}`;
  return <Tag className="heading">{c.props.text}</Tag>;
}

export function Paragraph({ c }) {
  return <p className={`paragraph ${c.props.role || ''}`}>{c.props.text}</p>;
}

export function Instruction({ c }) {
  return <p className="instruction">{c.props.text}</p>;
}

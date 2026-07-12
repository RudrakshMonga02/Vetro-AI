/** The bordered `bg-surface-panel border-line` container pattern,
 * previously repeated as raw Tailwind classes in 5+ places
 * (OffenderDetail's case cards, TrendsView sections, etc.). */
export default function Panel({ children, className = "", as: Tag = "div", ...rest }) {
  return (
    <Tag className={`border border-line rounded bg-surface-panel ${className}`} {...rest}>
      {children}
    </Tag>
  );
}

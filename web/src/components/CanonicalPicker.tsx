// Picks a canonical vocabulary value for a raw import string.
//
// Text-based for now (a <select>). This is the deliberate seam for the planned
// picture-matching UX: swap the <select> for a grid of formation/motion
// diagrams here and nothing else in the app needs to change -- it still just
// emits a canonical string via onChange.
type Props = {
  options: string[];
  value: string;
  onChange: (value: string) => void;
  label: string;
};

export default function CanonicalPicker({ options, value, onChange, label }: Props) {
  return (
    <select aria-label={label} value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">Choose…</option>
      {options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
}

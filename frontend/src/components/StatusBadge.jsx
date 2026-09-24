const LABELS = {
  answered: "Answered",
  partially_addressed: "Partially addressed",
  not_addressed: "Not addressed",
  not_in_transcripts: "Not in transcripts",
  unverified: "Unverified",
};

export default function StatusBadge({ status }) {
  return <span className={`badge badge-${status}`}>{LABELS[status] || status}</span>;
}

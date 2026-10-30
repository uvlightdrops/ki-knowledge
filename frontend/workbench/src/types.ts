export type Anchor = {
  start: number;
  end: number;
  exact: string;
  prefix: string;
  suffix: string;
  representation: string;
  offset_unit: string;
};
export type Annotation = Anchor & {
  id: string;
  title: string;
  category: string;
  tags: string[];
  note: string;
  version: number;
  etag: string;
  document_id: string;
  document_title: string;
  revision_id: string;
};
export type Relation = {
  id: string;
  source_id: string;
  target_id: string;
  type: string;
  rationale: string;
};
export type DocumentSummary = {
  id: string; title: string; kind: "reference" | "draft";
  etag: string;
  revision: { id: string; content_sha256: string };
};
export type Revision = { id: string; content_sha256: string; parent_id: string | null; cause: string; created_at: string };
export type Document = DocumentSummary & {
  etag: string;
  version: number;
  head_revision_id: string;
  origin_revision_id: string | null;
  revision: Revision & { text: string };
  annotations: Annotation[];
  historical_annotations: Annotation[];
  relations: Relation[];
};
export type Source = { id: string; title: string; folder: string; relative: string; registered: boolean };
export type ExcludedSource = Source & { reason: string; canonical_id?: string };
export type Bootstrap = { domain: string; apiBase: string; canCapture: boolean };
export type Metadata = { title: string; category: string; tags: string; note: string };

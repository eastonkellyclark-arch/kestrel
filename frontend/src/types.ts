export interface ListingSummary {
  id: number;
  listing_type: string;
  source: string;
  company: string;
  title: string;
  location: string | null;
  department: string | null;
  url: string | null;
  posted_at: string | null;
  is_remote: boolean;
  score: number | null;
  degree_hard_required: boolean;
  hygiene_score: number | null;
  skill_factor: number | null;
  scale_label: string | null;
}

export interface ListingDetail extends ListingSummary {
  description: string | null;
  description_quality: string;
  breakdown: {
    composite: number;
    hygiene_score: number;
    skill_factor: number;
    scale_label: string;
    dimensions: Record<string, { score: number; weight?: number }>;
  };
}

export interface IndexData {
  exported_at: string;
  count: number;
  listings: ListingSummary[];
}

export interface Filters {
  remote: boolean | null;
  minScore: number;
  degreeNotRequired: boolean;
  search: string;
}

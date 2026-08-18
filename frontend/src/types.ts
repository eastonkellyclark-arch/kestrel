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

export interface BreakdownDetail {
  skill_match?: {
    primary_hits?: string[];
    secondary_hits?: string[];
    bonus_hits?: string[];
    title_hits?: string[];
    quality_penalty?: boolean;
  };
  degree_posture?: { posture?: string; reason?: string };
  freshness?: { days_old?: number | null; reason?: string };
  location_fit?: { fit?: string; reason?: string };
  seniority_fit?: { level?: string; matched?: string };
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
    detail?: BreakdownDetail;
  };
}

export interface IndexData {
  exported_at: string;
  count: number;
  listings: ListingSummary[];
}

export interface Filters {
  listingType: 'all' | 'job' | 'gig';
  remote: boolean | null;
  minScore: number;
  degreeNotRequired: boolean;
  search: string;
}

export type TemplateSeed = {
  id: string;
  title: string;
  category: string;
  language: "ar" | "en" | "both";
  industry: string;
  lastUpdated: string;
  usageCount: number;
  gradient: [string, string];
};

export const TEMPLATE_SEED: TemplateSeed[] = [
  {
    id: "msa",
    title: "Master Service Agreement",
    category: "Commercial",
    language: "both",
    industry: "Technology",
    lastUpdated: "2026-07-01",
    usageCount: 42,
    gradient: ["#0F766E", "#14b8a6"],
  },
  {
    id: "nda",
    title: "Mutual NDA",
    category: "Legal",
    language: "both",
    industry: "All sectors",
    lastUpdated: "2026-06-15",
    usageCount: 88,
    gradient: ["#115e59", "#5eead4"],
  },
  {
    id: "sow",
    title: "Statement of Work",
    category: "Delivery",
    language: "en",
    industry: "Professional services",
    lastUpdated: "2026-05-20",
    usageCount: 31,
    gradient: ["#134e4a", "#2dd4bf"],
  },
  {
    id: "vendor",
    title: "Vendor Agreement",
    category: "Procurement",
    language: "ar",
    industry: "Retail",
    lastUpdated: "2026-04-10",
    usageCount: 19,
    gradient: ["#0d9488", "#99f6e4"],
  },
];

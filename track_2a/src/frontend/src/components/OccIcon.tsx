import { Baby, Briefcase, Car, ChefHat, Cog, HeartPulse, Laptop, Package, ShoppingBag, Sparkles, Stethoscope, Zap } from "lucide-react";

const ICONS = {
  briefcase: Briefcase,
  "heart-pulse": HeartPulse,
  "shopping-bag": ShoppingBag,
  laptop: Laptop,
  baby: Baby,
  zap: Zap,
  cog: Cog,
  "chef-hat": ChefHat,
  package: Package,
  stethoscope: Stethoscope,
  car: Car,
  sparkles: Sparkles,
} as const;

export function OccIcon({ name, size = 20, className }: { name: string; size?: number; className?: string }) {
  const Icon = ICONS[name as keyof typeof ICONS] ?? Briefcase;
  return <Icon size={size} className={className} />;
}

export const CONFIDENCE_FACES = ["😰", "😟", "😐", "🙂", "😎"];

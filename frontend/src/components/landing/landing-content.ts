import type { ElementType } from "react";
import { Brain, CheckSquare, Code, Compass, Lightbulb, Network, Rocket } from "lucide-react";

/**
 * Copy and structure for the landing page.
 *
 * These were array literals inside JSX, which meant the content could not be
 * read without parsing hundreds of lines of markup. Keeping it here also gives
 * each entry a stable `id` to key on, instead of the array index.
 */

export interface PipelineStage {
  id: string;
  step: string;
  title: string;
  desc: string;
  icon: ElementType;
}

export const PIPELINE_STAGES: PipelineStage[] = [
  {
    id: "idea",
    step: "01",
    title: "Idea",
    desc: "Raw business requirement ingestion and scope extraction.",
    icon: Lightbulb,
  },
  {
    id: "understand",
    step: "02",
    title: "Understand",
    desc: "Semantic breakdown of constraints and user flows.",
    icon: Brain,
  },
  {
    id: "reason",
    step: "03",
    title: "Reason",
    desc: "Multi-agent architectural negotiation and schema design.",
    icon: Network,
  },
  {
    id: "build",
    step: "04",
    title: "Build",
    desc: "Synthesis of robust APIs and user interface components.",
    icon: Code,
  },
  {
    id: "deploy",
    step: "05",
    title: "Deploy",
    desc: "Instantly accessible, production-ready operational system.",
    icon: Rocket,
  },
];

export interface Capability {
  id: string;
  title: string;
  desc: string;
  icon: ElementType;
}

export const CAPABILITIES: Capability[] = [
  {
    id: "semantic-ingestion",
    title: "Semantic Ingestion",
    desc: "Transform ambiguous business problems into perfectly structured requirements, mapped against enterprise ontology templates.",
    icon: Brain,
  },
  {
    id: "multi-agent-reasoning",
    title: "Multi-Agent Reasoning",
    desc: "Break complex problems into actionable components. The swarm negotiates architecture, database schemas, and UX flows simultaneously.",
    icon: Compass,
  },
  {
    id: "deterministic-synthesis",
    title: "Deterministic Synthesis",
    desc: "Generate a structured solution from the reasoning process. Deploy fully operational Next.js and FastAPI environments instantly.",
    icon: Code,
  },
  {
    id: "tangible-inspection",
    title: "Tangible Inspection",
    desc: "Explore generated artifacts, intermediate reasoning results, OpenAPI specs, and high-level designs in an interactive workspace.",
    icon: CheckSquare,
  },
];

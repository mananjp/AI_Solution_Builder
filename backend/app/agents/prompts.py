"""
AI Solution Builder — Agent System Prompts (Ultra-Compact for Groq Free Tier)

Each prompt is deliberately short (~50 tokens) to stay under Groq's 6,000 TPM limit.
7 LLM calls per pipeline × ~350 tokens of prompts = 2,450 tokens wasted on prompts alone.
Short prompts free up token budget for actual JSON output.
"""

BUSINESS_ANALYST_SYSTEM = """Analyze this business and return JSON:
{"business_description":"summary","industry":"logistics|retail|saas|healthcare|education|fintech|hr_consultancy|real_estate|manufacturing|general","business_size":"startup|sme|enterprise","business_stage":"idea|early|growth|mature","stakeholders":["list"],"pain_points":["list"],"identified_solutions":["modules the user explicitly asked for"],"confidence_score":0.0-1.0,"clarification_questions":["if confidence<0.7"],"analysis_summary":"brief summary"}
If vague, set identified_solutions=[] and lower confidence. Be concise."""


BUSINESS_RECOMMENDATION_SYSTEM = """Recommend 3-5 software modules for this business. Return JSON:
{"industry":"classified industry","recommended_modules":[{"module":"name","reason":"one-line why"}],"explanation":"brief why"}
Modules: public_website, crm, erp, hrms, attendance_system, inventory_management, ecommerce_storefront, order_fulfillment, client_onboarding_portal, project_management, invoicing_billing, analytics_dashboard, support_ticketing, document_management, booking_scheduler, gps_tracking, fleet_management, route_optimization, fuel_analytics, proof_of_delivery."""


SOLUTIONS_ARCHITECT_SYSTEM = """Generate HLD+LLD for these modules. Return JSON:
{"hld":{"title":"High-Level Design","system_overview":"2-3 sentence architecture overview","components":[{"name":"comp","description":"what","technology":"tech"}],"integrations":[{"from":"a","to":"b","protocol":"REST","description":"data flow"}],"deployment":{"environment":"cloud","services":["svc"],"scaling_strategy":"horizontal"},"security":{"authentication":"method","authorization":"method","encryption":"strategy"}},"lld":{"title":"Low-Level Design","modules":[{"name":"mod","description":"what","endpoints":[{"method":"GET","path":"/api/v1/x","description":"does"}],"data_models":["entities"]}]}}"""


UX_AGENT_SYSTEM = """Generate wireframes for these modules. Return JSON:
{"wireframes":[{"module":"name","screens":[{"name":"Screen","route":"/path","description":"purpose","layout":"sidebar|full-width","components":[{"type":"data_table|form|chart|card_grid|stat_card","title":"name","description":"what","fields":["f1"]}]}]}],"navigation":{"primary_menu":[{"label":"name","icon":"icon","route":"/path"}],"user_flows":[{"name":"flow","steps":["s1","s2"]}]},"design_tokens":{"primary_color":"#hex","secondary_color":"#hex","font_family":"Inter","border_radius":"8px"}}"""


DATABASE_API_AGENT_SYSTEM = """Generate ER diagram, DDL, and API spec. Return JSON:
{"er_diagram":{"entities":[{"name":"entity","fields":[{"name":"field","type":"UUID|VARCHAR(255)|INTEGER|TIMESTAMP|TEXT|BOOLEAN|JSONB|NUMERIC(10,2)","primary_key":false,"nullable":false,"foreign_key":null,"description":"stores"}]}],"relationships":[{"from":"a","to":"b","type":"one-to-many","via":null}]},"schema_ddl":"CREATE TABLE statements as string","api_endpoints":[{"method":"GET|POST|PUT|DELETE","path":"/api/v1/x","description":"does","request_body":null,"response":{"field":"type"}}]}"""


BLUEPRINT_GENERATOR_SYSTEM = """Synthesize a solution blueprint. Return JSON:
{"executive_summary":"what was built and why","roadmap":{"phases":[{"name":"Phase","duration":"X weeks","modules":["mod"],"milestones":["milestone"],"deliverables":["item"]}],"total_duration":"X weeks"},"effort_estimation":[{"module":"name","effort_days":0,"complexity":"low|medium|high"}],"risks":[{"risk":"desc","impact":"high|medium|low","mitigation":"fix"}],"success_metrics":[{"metric":"what","target":"value","measurement_method":"how"}],"next_steps":["action"]}"""


PROCESS_INTELLIGENCE_SYSTEM = """Generate BPMN workflows and process flows. Return JSON:
{"bpmn":{"name":"Process","xml":"BPMN 2.0 XML string","flows":[{"id":"f1","name":"Flow name"}]},"react_flow":{"nodes":[{"id":"n1","type":"start|task|gateway|end","position":{"x":0,"y":0},"data":{"label":"name"}}],"edges":[{"id":"e1","source":"n1","target":"n2"}]},"swimlanes":[{"id":"lane","label":"Role","tasks":["n1"]}],"bottlenecks":[{"module":"name","severity":"low|medium|high","reason":"why","recommendation":"fix"}]}"""


CODE_SYNTHESIZER_SYSTEM = """Generate executable schema and module manifests. Return JSON:
{"generated_schema":{"declarative":{"tables":[{"name":"table","columns":[{"name":"col","type":"VARCHAR(255)","primary_key":false,"nullable":false,"foreign_key":null}]}]},"ddl":"CREATE TABLE statements"},"workable_modules":[{"module":"name","path":"/path","entities":["entity"],"summary":"CRUD exposed"}],"code_manifest":{"framework":"FastAPI + Next.js","tree":["backend/app.py","frontend/pages/x.tsx"],"stack_version":"2026.1"}}"""

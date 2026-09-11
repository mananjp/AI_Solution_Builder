"""
AI Solution Builder — Industry Template Library

Seed data for the Business Recommendation Agent.
Maps industry verticals to common software modules.
"""

INDUSTRY_TEMPLATES = {
    "hr_consultancy": {
        "core_entities": ["candidates", "clients", "placements", "interviews", "timesheets"],
        "recommended_modules": [
            {"module": "public_website", "reason": "Client & candidate acquisition"},
            {"module": "crm", "reason": "Track client relationships and deal pipeline"},
            {"module": "attendance_system", "reason": "Manage placed-candidate timesheets"},
            {"module": "client_onboarding_portal", "reason": "Structured intake for new clients"},
            {"module": "invoicing_billing", "reason": "Bill clients for placements"},
            {
                "module": "analytics_dashboard",
                "reason": "Track KPIs: fill rate, time-to-hire, revenue",
            },
        ],
    },
    "d2c_retail": {
        "core_entities": ["products", "orders", "customers", "inventory", "shipments"],
        "recommended_modules": [
            {"module": "ecommerce_storefront", "reason": "Sell direct to consumer online"},
            {"module": "inventory_management", "reason": "Track stock across SKUs and warehouses"},
            {"module": "order_fulfillment", "reason": "Coordinate shipping, tracking & returns"},
            {"module": "crm", "reason": "Customer segmentation and lifecycle management"},
            {"module": "analytics_dashboard", "reason": "Sales analytics, conversion funnels, CAC"},
        ],
    },
    "saas_startup": {
        "core_entities": ["users", "subscriptions", "features", "support_tickets"],
        "recommended_modules": [
            {"module": "public_website", "reason": "Product marketing and signup funnel"},
            {"module": "analytics_dashboard", "reason": "User metrics, MRR, churn, retention"},
            {"module": "support_ticketing", "reason": "Customer support and issue tracking"},
            {
                "module": "invoicing_billing",
                "reason": "Subscription billing and payment management",
            },
            {"module": "project_management", "reason": "Internal sprint and roadmap tracking"},
        ],
    },
    "healthcare_clinic": {
        "core_entities": ["patients", "doctors", "appointments", "records", "prescriptions"],
        "recommended_modules": [
            {"module": "booking_scheduler", "reason": "Patient appointment booking"},
            {"module": "public_website", "reason": "Clinic information and online booking"},
            {"module": "document_management", "reason": "Patient records and medical history"},
            {"module": "invoicing_billing", "reason": "Patient billing and insurance claims"},
            {
                "module": "analytics_dashboard",
                "reason": "Patient flow, revenue, utilization metrics",
            },
        ],
    },
    "education_institute": {
        "core_entities": ["students", "courses", "teachers", "enrollments", "grades"],
        "recommended_modules": [
            {"module": "public_website", "reason": "Course catalog and admissions portal"},
            {"module": "attendance_system", "reason": "Student and teacher attendance tracking"},
            {"module": "project_management", "reason": "Course management and curriculum planning"},
            {
                "module": "analytics_dashboard",
                "reason": "Student performance and enrollment analytics",
            },
            {"module": "invoicing_billing", "reason": "Fee management and payment collection"},
        ],
    },
    "logistics_company": {
        "core_entities": ["shipments", "drivers", "vehicles", "routes", "warehouses"],
        "recommended_modules": [
            {"module": "order_fulfillment", "reason": "Shipment tracking and delivery management"},
            {"module": "inventory_management", "reason": "Warehouse and cargo management"},
            {"module": "analytics_dashboard", "reason": "Fleet utilization, delivery KPIs, costs"},
            {"module": "crm", "reason": "Client relationship and contract management"},
            {"module": "invoicing_billing", "reason": "Freight billing and rate management"},
        ],
    },
    "real_estate": {
        "core_entities": ["properties", "listings", "leads", "agents", "transactions"],
        "recommended_modules": [
            {"module": "public_website", "reason": "Property listings and lead capture"},
            {"module": "crm", "reason": "Lead nurturing and deal pipeline"},
            {"module": "booking_scheduler", "reason": "Property viewing appointments"},
            {"module": "document_management", "reason": "Contracts, agreements, and legal docs"},
            {"module": "analytics_dashboard", "reason": "Sales pipeline and market analytics"},
        ],
    },
    "restaurant_food": {
        "core_entities": ["menu_items", "orders", "customers", "tables", "inventory"],
        "recommended_modules": [
            {"module": "public_website", "reason": "Menu display and online ordering"},
            {"module": "inventory_management", "reason": "Kitchen stock and ingredient tracking"},
            {"module": "order_fulfillment", "reason": "Order management for dine-in and delivery"},
            {"module": "booking_scheduler", "reason": "Table reservations"},
            {"module": "analytics_dashboard", "reason": "Revenue, popular items, peak hours"},
        ],
    },
    "consulting_agency": {
        "core_entities": ["clients", "projects", "consultants", "proposals", "invoices"],
        "recommended_modules": [
            {"module": "public_website", "reason": "Service showcase and lead generation"},
            {"module": "crm", "reason": "Client and prospect management"},
            {"module": "project_management", "reason": "Engagement and deliverable tracking"},
            {"module": "invoicing_billing", "reason": "Project billing and expense tracking"},
            {"module": "document_management", "reason": "Proposals, reports, and deliverables"},
            {"module": "analytics_dashboard", "reason": "Utilization rates and revenue analytics"},
        ],
    },
}

# Generic fallback for unrecognized industries
GENERIC_TEMPLATE = {
    "core_entities": ["users", "customers", "products", "orders"],
    "recommended_modules": [
        {"module": "public_website", "reason": "Online presence and customer acquisition"},
        {"module": "crm", "reason": "Customer relationship management"},
        {"module": "invoicing_billing", "reason": "Billing and payment management"},
        {"module": "analytics_dashboard", "reason": "Business performance metrics"},
    ],
}

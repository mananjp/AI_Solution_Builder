-- AI Solution Builder PostgreSQL DDL Schema
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE audit_logs (
	id UUID NOT NULL, 
	user_id UUID, 
	org_id UUID, 
	action VARCHAR(20) NOT NULL, 
	resource VARCHAR(500) NOT NULL, 
	request_id VARCHAR(64), 
	method VARCHAR(10) NOT NULL, 
	path VARCHAR(500) NOT NULL, 
	ip_address VARCHAR(64), 
	status_code INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE plans (
	id UUID NOT NULL, 
	name VARCHAR(50) NOT NULL, 
	monthly_credits INTEGER NOT NULL, 
	max_workable_systems INTEGER NOT NULL, 
	price_usd NUMERIC(10, 2) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);

CREATE TABLE scan_records (
	id UUID NOT NULL, 
	sha256 VARCHAR(64), 
	url VARCHAR(2048), 
	target VARCHAR(10) NOT NULL, 
	source VARCHAR(40) NOT NULL, 
	verdict VARCHAR(16) NOT NULL, 
	findings JSONB NOT NULL, 
	scanned_bytes INTEGER NOT NULL, 
	from_cache BOOLEAN NOT NULL, 
	user_id UUID, 
	org_id UUID, 
	request_id VARCHAR(64), 
	duration_ms INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE organizations (
	id UUID NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	plan_id UUID, 
	credits_remaining INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(plan_id) REFERENCES plans (id)
);

CREATE TABLE payment_orders (
	id UUID NOT NULL, 
	gateway VARCHAR(20) NOT NULL, 
	gateway_order_id VARCHAR(64) NOT NULL, 
	org_id UUID NOT NULL, 
	amount INTEGER NOT NULL, 
	currency VARCHAR(3) NOT NULL, 
	credits INTEGER NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	payment_id VARCHAR(64), 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	captured_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE
);

CREATE TABLE users (
	id UUID NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	full_name VARCHAR(255) NOT NULL, 
	hashed_password VARCHAR(255), 
	role VARCHAR(50) NOT NULL, 
	auth_provider VARCHAR(50) NOT NULL, 
	provider_user_id VARCHAR(255), 
	auth_issuer VARCHAR(255), 
	email_verified BOOLEAN NOT NULL, 
	is_anonymous BOOLEAN NOT NULL, 
	settings JSONB, 
	is_active BOOLEAN NOT NULL, 
	org_id UUID, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_users_auth0_identity UNIQUE (auth_issuer, provider_user_id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id)
);

CREATE TABLE workspaces (
	id UUID NOT NULL, 
	org_id UUID NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	description TEXT, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE
);

CREATE TABLE recommendation_events (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	industry_classified VARCHAR(100), 
	modules_proposed JSONB, 
	modules_accepted JSONB, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
);

CREATE TABLE solutions (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	title VARCHAR(500) NOT NULL, 
	description TEXT, 
	status VARCHAR(50) NOT NULL, 
	approval_status VARCHAR(50), 
	approved_by UUID, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	approval_comments TEXT, 
	approval_snapshot JSONB, 
	ui_theme JSONB, 
	ai_state JSONB, 
	conversation_history JSONB, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE, 
	FOREIGN KEY(approved_by) REFERENCES users (id)
);

CREATE TABLE context_chunks (
	id UUID NOT NULL, 
	org_id UUID NOT NULL, 
	solution_id UUID, 
	source_type VARCHAR(50) NOT NULL, 
	source_name VARCHAR(500) NOT NULL, 
	chunk_index INTEGER NOT NULL, 
	content TEXT NOT NULL, 
	detected_lang VARCHAR(10) NOT NULL, 
	embedding VECTOR(384), 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(solution_id) REFERENCES solutions (id) ON DELETE CASCADE
);

CREATE TABLE credit_transactions (
	id UUID NOT NULL, 
	org_id UUID NOT NULL, 
	action_type VARCHAR(100) NOT NULL, 
	credits_used INTEGER NOT NULL, 
	description TEXT, 
	solution_id UUID, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(solution_id) REFERENCES solutions (id) ON DELETE SET NULL
);

CREATE TABLE mvp_builds (
	id UUID NOT NULL, 
	solution_id UUID NOT NULL, 
	build_number INTEGER NOT NULL, 
	status VARCHAR(50) NOT NULL, 
	opencode_session_id VARCHAR(255), 
	workspace_path VARCHAR(1000) NOT NULL, 
	file_list JSONB, 
	app_config JSONB, 
	file_count INTEGER NOT NULL, 
	repo_url VARCHAR(1000), 
	storage_key VARCHAR(1000), 
	error_message TEXT, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_mvp_build_solution_number UNIQUE (solution_id, build_number), 
	FOREIGN KEY(solution_id) REFERENCES solutions (id) ON DELETE CASCADE
);

CREATE TABLE solution_artifacts (
	id UUID NOT NULL, 
	solution_id UUID NOT NULL, 
	artifact_type VARCHAR(100) NOT NULL, 
	title VARCHAR(500) NOT NULL, 
	content JSONB NOT NULL, 
	content_text TEXT, 
	version INTEGER NOT NULL, 
	parent_version_id UUID, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(solution_id) REFERENCES solutions (id) ON DELETE CASCADE, 
	FOREIGN KEY(parent_version_id) REFERENCES solution_artifacts (id)
);

CREATE TABLE workable_schemas (
	id UUID NOT NULL, 
	solution_id UUID NOT NULL, 
	schema_name VARCHAR(100) NOT NULL, 
	modules JSONB NOT NULL, 
	status VARCHAR(50) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (solution_id), 
	FOREIGN KEY(solution_id) REFERENCES solutions (id) ON DELETE CASCADE, 
	UNIQUE (schema_name)
);

CREATE TABLE artifact_comments (
	id UUID NOT NULL, 
	artifact_id UUID NOT NULL, 
	author_id UUID NOT NULL, 
	body TEXT NOT NULL, 
	resolved BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(artifact_id) REFERENCES solution_artifacts (id) ON DELETE CASCADE
);

CREATE TABLE build_jobs (
	id UUID NOT NULL, 
	build_id UUID NOT NULL, 
	status VARCHAR(50) NOT NULL, 
	attempts INTEGER NOT NULL, 
	max_attempts INTEGER NOT NULL, 
	claimed_by VARCHAR(255), 
	claimed_at TIMESTAMP WITH TIME ZONE, 
	heartbeat_at TIMESTAMP WITH TIME ZONE, 
	error_message TEXT, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(build_id) REFERENCES mvp_builds (id) ON DELETE CASCADE
);

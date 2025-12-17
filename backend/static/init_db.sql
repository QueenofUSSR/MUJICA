-- search_path: "$user", public


CREATE TABLE agent_roles (
	id SERIAL NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	description TEXT, 
	capabilities JSON, 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	CONSTRAINT agent_roles_pkey PRIMARY KEY (id), 
	CONSTRAINT agent_roles_name_key UNIQUE NULLS DISTINCT (name)
);

INSERT INTO agent_roles (name, description, capabilities, is_active, created_at, updated_at) VALUES ($dump$retriever$dump$, $dump$检索相关示例$dump$, $dump${"type": "retrieval"}$dump$::jsonb, true, '2025-12-14 10:32:39.531515', '2025-12-14 10:32:39.531515');
INSERT INTO agent_roles (name, description, capabilities, is_active, created_at, updated_at) VALUES ($dump$planner$dump$, $dump$生成多候选计划$dump$, $dump${"type": "planning"}$dump$::jsonb, true, '2025-12-14 10:32:39.531515', '2025-12-14 10:32:39.531515');
INSERT INTO agent_roles (name, description, capabilities, is_active, created_at, updated_at) VALUES ($dump$coder$dump$, $dump$根据计划生成代码$dump$, $dump${"type": "coding"}$dump$::jsonb, true, '2025-12-14 10:32:39.531515', '2025-12-14 10:32:39.531515');
INSERT INTO agent_roles (name, description, capabilities, is_active, created_at, updated_at) VALUES ($dump$debugger$dump$, $dump$基于样例调试并修复$dump$, $dump${"type": "debugging"}$dump$::jsonb, true, '2025-12-14 10:32:39.531515', '2025-12-14 10:32:39.531515');


CREATE TABLE users (
	id SERIAL NOT NULL, 
	username VARCHAR(50) NOT NULL, 
	hashed_password VARCHAR(100) NOT NULL, 
	phone VARCHAR(20), 
	email VARCHAR(50), 
	avatar VARCHAR(60), 
	is_active BOOLEAN NOT NULL, 
	CONSTRAINT users_pkey PRIMARY KEY (id), 
	CONSTRAINT users_username_key UNIQUE NULLS DISTINCT (username)
);

INSERT INTO users (username, hashed_password, phone, email, avatar, is_active) VALUES ($dump$陈世有$dump$, $dump$$2b$12$mTipNff1//uFpWQWPA5gEOjEFmmE2zyUHy1bI./vAFAHSLG3bEmLm$dump$, $dump$14774710365$dump$, NULL, $dump$/static/avatars/user_1.jpg$dump$, true);
INSERT INTO users (username, hashed_password, phone, email, avatar, is_active) VALUES ($dump$demo$dump$, $dump$demo$dump$, NULL, NULL, NULL, true);


CREATE TABLE agent_sessions (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	model_id VARCHAR(80), 
	status VARCHAR(40) NOT NULL, 
	metadata JSON, 
	final_result JSON, 
	summary_title VARCHAR(200), 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	CONSTRAINT agent_sessions_pkey PRIMARY KEY (id), 
	CONSTRAINT agent_sessions_user_id_fkey FOREIGN KEY(user_id) REFERENCES users (id)
);


CREATE TABLE agent_tasks (
	id SERIAL NOT NULL, 
	session_id INTEGER NOT NULL, 
	parent_id INTEGER, 
	assigned_role_id INTEGER, 
	title VARCHAR(200) NOT NULL, 
	description TEXT, 
	status VARCHAR(40) NOT NULL, 
	confidence DOUBLE PRECISION, 
	attempt_count INTEGER NOT NULL, 
	max_attempts INTEGER NOT NULL, 
	result JSON, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	CONSTRAINT agent_tasks_pkey PRIMARY KEY (id), 
	CONSTRAINT agent_tasks_assigned_role_id_fkey FOREIGN KEY(assigned_role_id) REFERENCES agent_roles (id), 
	CONSTRAINT agent_tasks_parent_id_fkey FOREIGN KEY(parent_id) REFERENCES agent_tasks (id), 
	CONSTRAINT agent_tasks_session_id_fkey FOREIGN KEY(session_id) REFERENCES agent_sessions (id)
);


CREATE TABLE agent_task_logs (
	id SERIAL NOT NULL, 
	session_id INTEGER NOT NULL, 
	task_id INTEGER, 
	role_id INTEGER, 
	level VARCHAR(32) NOT NULL, 
	message TEXT NOT NULL, 
	payload JSON, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	CONSTRAINT agent_task_logs_pkey PRIMARY KEY (id), 
	CONSTRAINT agent_task_logs_role_id_fkey FOREIGN KEY(role_id) REFERENCES agent_roles (id), 
	CONSTRAINT agent_task_logs_session_id_fkey FOREIGN KEY(session_id) REFERENCES agent_sessions (id), 
	CONSTRAINT agent_task_logs_task_id_fkey FOREIGN KEY(task_id) REFERENCES agent_tasks (id)
);


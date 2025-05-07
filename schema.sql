CREATE TABLE db_connectors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    db_type TEXT NOT NULL,
    host TEXT NOT NULL,
    port INTEGER NOT NULL,
    db_name TEXT NOT NULL,
    username TEXT NOT NULL,
    password TEXT NOT NULL,
    active INTEGER DEFAULT 1
, user_id INTEGER);
CREATE TABLE api_endpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint_name TEXT UNIQUE NOT NULL,
    connector_id INTEGER NOT NULL,
    sql_query TEXT NOT NULL,
    active INTEGER DEFAULT 1
, parameters TEXT DEFAULT '', auth_token TEXT DEFAULT '', user_id INTEGER);
CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL
, surname TEXT, name TEXT, patronymic TEXT, security_answer TEXT, role TEXT DEFAULT 'user');
CREATE TABLE api_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token TEXT UNIQUE NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT,
    comment TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE TABLE token_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    comment TEXT,
    requested_at TEXT NOT NULL,
    status TEXT DEFAULT 'pending', -- pending, approved, rejected
    FOREIGN KEY (user_id) REFERENCES users(id)
);

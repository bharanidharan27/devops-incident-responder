PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS incidents (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  external_id  TEXT UNIQUE,
  status       TEXT NOT NULL CHECK(status IN ('OPEN', 'IN_PROGRESS', 'DONE', 'FAILED')),
  service      TEXT NOT NULL,
  environment  TEXT NOT NULL,
  severity     TEXT NOT NULL,
  title        TEXT NOT NULL DEFAULT '',
  description  TEXT NOT NULL DEFAULT '',
  alert_type   TEXT NOT NULL DEFAULT '',
  source       TEXT NOT NULL DEFAULT 'manual',
  payload_json TEXT NOT NULL DEFAULT '{}',
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_steps (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  incident_id INTEGER NOT NULL,
  agent       TEXT NOT NULL,
  phase       TEXT NOT NULL,
  message     TEXT NOT NULL,
  data_json   TEXT NOT NULL DEFAULT '{}',
  ts          TEXT NOT NULL,
  status      TEXT,
  FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reports (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  incident_id INTEGER NOT NULL,
  report_json TEXT NOT NULL,
  report_md   TEXT NOT NULL,
  created_at  TEXT NOT NULL,
  FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status, id);
CREATE INDEX IF NOT EXISTS idx_incidents_external_id ON incidents(external_id);
CREATE INDEX IF NOT EXISTS idx_steps_inc_ts ON agent_steps(incident_id, ts);
CREATE INDEX IF NOT EXISTS idx_reports_inc_dt ON reports(incident_id, created_at);

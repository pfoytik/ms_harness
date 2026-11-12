-- MS Harness — tool-agnostic samples database schema

CREATE TABLE IF NOT EXISTS sweeps (
    sweep_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    sweep_type   TEXT    NOT NULL,  -- 'lhs', 'targeted', 'manual'
    n_planned    INTEGER NOT NULL,
    n_complete   INTEGER DEFAULT 0,
    status       TEXT    DEFAULT 'pending',
    notes        TEXT,
    created_at   TEXT    NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS scenarios (
    scenario_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    sweep_id     INTEGER NOT NULL REFERENCES sweeps(sweep_id),
    status       TEXT    DEFAULT 'pending',
    created_at   TEXT    NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS inputs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id  INTEGER NOT NULL REFERENCES scenarios(scenario_id),
    parameter    TEXT    NOT NULL,
    value        REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS outputs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id  INTEGER NOT NULL REFERENCES scenarios(scenario_id),
    metric       TEXT    NOT NULL,
    value        REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS findings (
    finding_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    sweep_id     INTEGER NOT NULL REFERENCES sweeps(sweep_id),
    report_json  TEXT    NOT NULL,
    created_at   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_outputs (
    ai_output_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sweep_id     INTEGER REFERENCES sweeps(sweep_id),
    kind         TEXT    NOT NULL,  -- 'interpretation', 'proposal'
    content      TEXT    NOT NULL,
    created_at   TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_inputs_scenario  ON inputs(scenario_id);
CREATE INDEX IF NOT EXISTS idx_outputs_scenario ON outputs(scenario_id);
CREATE INDEX IF NOT EXISTS idx_scenarios_sweep  ON scenarios(sweep_id);

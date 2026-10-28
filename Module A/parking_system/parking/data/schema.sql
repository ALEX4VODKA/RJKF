CREATE TABLE IF NOT EXISTS admin (
    admin_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username       TEXT NOT NULL UNIQUE,
    password_hash  TEXT NOT NULL,
    salt           TEXT NOT NULL,
    role           TEXT NOT NULL CHECK (role IN ('admin', 'operator')),
    fail_count     INTEGER NOT NULL DEFAULT 0 CHECK (fail_count >= 0),
    locked_until   TEXT,
    must_change_password INTEGER NOT NULL DEFAULT 1 CHECK (must_change_password IN (0, 1)),
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS vehicle (
    plate_no       TEXT PRIMARY KEY,
    vehicle_type   TEXT NOT NULL,
    plate_color    TEXT NOT NULL CHECK (plate_color IN ('blue', 'yellow', 'green', 'white', 'black', 'other')),
    owner_name     TEXT,
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS fee_rule (
    rule_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_type       TEXT NOT NULL,
    version            INTEGER NOT NULL CHECK (version > 0),
    free_minutes       INTEGER NOT NULL CHECK (free_minutes BETWEEN 0 AND 120),
    first_hours        INTEGER NOT NULL CHECK (first_hours BETWEEN 1 AND 24),
    first_price_cents  INTEGER NOT NULL CHECK (first_price_cents > 0),
    extra_price_cents  INTEGER NOT NULL CHECK (extra_price_cents > 0),
    day_cap_cents      INTEGER NOT NULL CHECK (day_cap_cents >= first_price_cents),
    effective_at       TEXT NOT NULL,
    active             INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    supersedes_rule_id INTEGER,
    created_by         INTEGER,
    created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (vehicle_type, version),
    FOREIGN KEY (supersedes_rule_id) REFERENCES fee_rule(rule_id),
    FOREIGN KEY (created_by) REFERENCES admin(admin_id) ON DELETE SET NULL
);

INSERT INTO fee_rule (
    vehicle_type, version, free_minutes, first_hours,
    first_price_cents, extra_price_cents, day_cap_cents, effective_at
)
SELECT '小型车', 1, 15, 2, 500, 300, 3000, strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
WHERE NOT EXISTS (
    SELECT 1 FROM fee_rule WHERE vehicle_type = '小型车'
);

CREATE TABLE IF NOT EXISTS parking_record (
    record_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    plate_no               TEXT NOT NULL,
    vehicle_type           TEXT NOT NULL,
    plate_color            TEXT NOT NULL,
    entry_time             TEXT NOT NULL,
    entry_photo            TEXT,
    entry_source           TEXT NOT NULL DEFAULT 'manual' CHECK (entry_source IN ('recognition', 'manual', 'demo')),
    fee_rule_id            INTEGER NOT NULL,
    rule_free_minutes      INTEGER NOT NULL,
    rule_first_hours       INTEGER NOT NULL,
    rule_first_price_cents INTEGER NOT NULL,
    rule_extra_price_cents INTEGER NOT NULL,
    rule_day_cap_cents     INTEGER NOT NULL,
    billing_cutoff_at      TEXT,
    exit_photo             TEXT,
    duration_minutes       INTEGER CHECK (duration_minutes IS NULL OR duration_minutes >= 0),
    fee_cents              INTEGER CHECK (fee_cents IS NULL OR fee_cents >= 0),
    payment_status         TEXT NOT NULL DEFAULT 'unbilled'
                           CHECK (payment_status IN ('unbilled', 'unpaid', 'paid', 'authorized')),
    paid_cents             INTEGER NOT NULL DEFAULT 0 CHECK (paid_cents >= 0),
    paid_at                TEXT,
    release_status         TEXT NOT NULL DEFAULT 'not_released'
                           CHECK (release_status IN ('not_released', 'released', 'passed')),
    release_type           TEXT CHECK (release_type IN ('auto', 'free', 'authorized')),
    release_reason         TEXT,
    released_by            INTEGER,
    released_at            TEXT,
    exit_time              TEXT,
    created_at             TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at             TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (plate_no) REFERENCES vehicle(plate_no),
    FOREIGN KEY (fee_rule_id) REFERENCES fee_rule(rule_id),
    FOREIGN KEY (released_by) REFERENCES admin(admin_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS bill_daily_detail (
    detail_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id             INTEGER NOT NULL,
    billing_date          TEXT NOT NULL,
    period_start          TEXT NOT NULL,
    period_end            TEXT NOT NULL,
    duration_minutes      INTEGER NOT NULL CHECK (duration_minutes >= 0),
    fee_before_cap_cents  INTEGER NOT NULL CHECK (fee_before_cap_cents >= 0),
    prior_daily_fee_cents INTEGER NOT NULL DEFAULT 0 CHECK (prior_daily_fee_cents >= 0),
    charged_cents         INTEGER NOT NULL CHECK (charged_cents >= 0),
    created_at            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (record_id, billing_date),
    FOREIGN KEY (record_id) REFERENCES parking_record(record_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS operation_log (
    log_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id      INTEGER,
    action        TEXT NOT NULL,
    target        TEXT,
    before_value  TEXT,
    after_value   TEXT,
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (admin_id) REFERENCES admin(admin_id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uk_parking_record_open
    ON parking_record(plate_no) WHERE exit_time IS NULL;
CREATE INDEX IF NOT EXISTS idx_parking_record_entry
    ON parking_record(entry_time);
CREATE INDEX IF NOT EXISTS idx_parking_record_exit
    ON parking_record(exit_time);
CREATE INDEX IF NOT EXISTS idx_parking_record_plate
    ON parking_record(plate_no, exit_time);
CREATE INDEX IF NOT EXISTS idx_fee_rule_lookup
    ON fee_rule(vehicle_type, active, effective_at DESC);
CREATE INDEX IF NOT EXISTS idx_operation_log_time
    ON operation_log(created_at);

-- PitchShift owns this schema only. Safe to use beside another application's tables.
CREATE SCHEMA IF NOT EXISTS pitchshift;

CREATE TABLE IF NOT EXISTS pitchshift.pitches (
    game_pk bigint NOT NULL,
    at_bat_number integer NOT NULL,
    pitch_number integer NOT NULL,
    game_date date NOT NULL,
    pitcher_id bigint NOT NULL,
    pitcher_name text,
    pitch_type text NOT NULL,
    batter_stand text,
    pitcher_throws text,
    release_speed real,
    release_pos_x real,
    release_pos_z real,
    pfx_x real,
    pfx_z real,
    plate_x real,
    plate_z real,
    sz_top real,
    sz_bot real,
    description text,
    PRIMARY KEY (game_pk, at_bat_number, pitch_number)
);

CREATE INDEX IF NOT EXISTS pitches_pitcher_date_idx
    ON pitchshift.pitches (pitcher_id, game_date DESC, game_pk DESC);

CREATE TABLE IF NOT EXISTS pitchshift.snapshots (
    content_sha256 char(64) PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now(),
    report jsonb NOT NULL
);

-- SQL window functions make the retained sequence available for ad hoc research.
-- The Python pipeline defines the exact disjoint comparison windows and inference.
CREATE OR REPLACE VIEW pitchshift.pitch_sequence AS
SELECT *, row_number() OVER (
    PARTITION BY pitcher_id
    ORDER BY game_date DESC, game_pk DESC, at_bat_number DESC, pitch_number DESC
) AS pitcher_pitch_recency
FROM pitchshift.pitches;

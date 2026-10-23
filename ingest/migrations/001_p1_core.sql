-- P1 core schema: airline reference, poll log, raw positions, latest state per aircraft.
-- Units are SI as OpenSky sends them (metres, m/s); the dashboard converts for display.
-- Only allowlisted airline traffic is ever written here (docs/adr/0002).

CREATE TABLE airlines (
    icao  text PRIMARY KEY,
    iata  text,
    name  text NOT NULL,
    kind  text NOT NULL
);

-- One row per external call, successful or not. Drives budget checks and the health page.
CREATE TABLE polls (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source            text        NOT NULL,          -- 'opensky' | 'replay'
    ts                timestamptz NOT NULL DEFAULT now(),
    data_time         timestamptz,                   -- OpenSky response "time"
    http_status       integer,
    received          integer,
    kept              integer,
    latency_ms        integer,
    credits_remaining integer,
    error             text
);
CREATE INDEX polls_ts ON polls (ts);

-- Airline-shaped callsign prefixes that were dropped for not being on the allowlist.
-- Prefix and count only: used to maintain the allowlist, never to identify aircraft.
CREATE TABLE unmatched_prefixes (
    day     date    NOT NULL,
    prefix  text    NOT NULL,
    count   integer NOT NULL,
    PRIMARY KEY (day, prefix)
);

-- Raw positions, partitioned by day on the position timestamp. Partitions are created
-- ahead and dropped after 48 h by at_ingest.maintenance.
CREATE TABLE positions (
    icao24     text        NOT NULL,
    ts         timestamptz NOT NULL,                 -- OpenSky time_position
    poll_id    bigint      NOT NULL,
    callsign   text        NOT NULL,
    lat        double precision NOT NULL,
    lon        double precision NOT NULL,
    baro_alt   real,
    geo_alt    real,
    velocity   real,
    track      real,
    vrate      real,
    on_ground  boolean     NOT NULL,
    squawk     text,
    PRIMARY KEY (icao24, ts)
) PARTITION BY RANGE (ts);

-- Latest known state per aircraft: what the map reads.
CREATE TABLE aircraft_state (
    icao24     text PRIMARY KEY,
    callsign   text        NOT NULL,
    ts         timestamptz NOT NULL,                 -- position time of the latest report
    last_seen  timestamptz NOT NULL,                 -- OpenSky last_contact
    poll_id    bigint      NOT NULL,
    lat        double precision NOT NULL,
    lon        double precision NOT NULL,
    baro_alt   real,
    geo_alt    real,
    velocity   real,
    track      real,
    vrate      real,
    on_ground  boolean     NOT NULL,
    squawk     text
);
CREATE INDEX aircraft_state_last_seen ON aircraft_state (last_seen);

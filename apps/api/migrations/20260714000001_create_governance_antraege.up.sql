-- Governance: allgemeines Antragssystem (erster Antragstyp: Weberantrag).
--
-- PostgreSQL ist die kanonische Wahrheit für Anträge, Vetos, Stimmen und
-- Gesprächsraum-Beiträge. Ohne Datenbank arbeiten die Governance-Endpunkte
-- fail-closed; es gibt keinen JSONL-Fallback für diese Tabellen.
--
-- Fristenmodell (Weberantrag):
--   status='consent' : offene Konsentphase bis consent_until (7 Tage).
--   status='voting'  : nach mindestens einem Veto beginnt mit Ablauf der
--                      Konsentphase eine Beratungs- und Abstimmungsphase bis
--                      voting_until (weitere 7 Tage).
--   status='accepted'/'rejected': serverseitig und idempotent finalisiert.
--
-- Governance ist nur bei kanonischer PostgreSQL-Accountwahrheit aktiv. Der
-- Weberantrag verweist daher auf eine bestehende Gastidentität. Anzeigenamen
-- werden dennoch als Verfahrenssnapshot gespeichert, damit die Historie nicht
-- von späteren Profiländerungen abhängt.

CREATE TABLE governance_proposals (
    id                   UUID        PRIMARY KEY,
    kind                 TEXT        NOT NULL CHECK (kind = 'weberantrag'),
    applicant_account_id TEXT        NOT NULL REFERENCES domain_accounts (id) ON DELETE CASCADE,
    -- Anzeigename zum Antragszeitpunkt: Informationsseite und Listen dürfen
    -- nicht vom (ggf. JSONL-basierten) Account-Store abhängen.
    applicant_title      TEXT        NOT NULL,
    summary              TEXT        CHECK (summary IS NULL OR char_length(summary) <= 2000),
    status               TEXT        NOT NULL DEFAULT 'consent'
                                     CHECK (status IN ('consent', 'voting', 'accepted', 'rejected')),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    consent_until        TIMESTAMPTZ NOT NULL,
    voting_until         TIMESTAMPTZ,
    finalized_at         TIMESTAMPTZ,
    CONSTRAINT governance_proposals_phase_consistent CHECK (
        (status = 'consent' AND voting_until IS NULL AND finalized_at IS NULL)
        OR (status = 'voting' AND voting_until IS NOT NULL AND finalized_at IS NULL)
        OR (status IN ('accepted', 'rejected') AND finalized_at IS NOT NULL)
    )
);

-- Doppelantrag: je Account höchstens ein offener Antrag pro Antragsart.
CREATE UNIQUE INDEX governance_proposals_one_open_per_applicant
    ON governance_proposals (applicant_account_id, kind)
    WHERE status IN ('consent', 'voting');

-- Fristauswertung: der Sweeper fragt nur fällige offene Anträge ab.
CREATE INDEX governance_proposals_due_consent
    ON governance_proposals (consent_until)
    WHERE status = 'consent';
CREATE INDEX governance_proposals_due_voting
    ON governance_proposals (voting_until)
    WHERE status = 'voting';

-- Begründetes Veto: höchstens eines je Weber und Antrag.
CREATE TABLE governance_vetoes (
    proposal_id      UUID        NOT NULL REFERENCES governance_proposals (id) ON DELETE CASCADE,
    weber_account_id TEXT        NOT NULL,
    weber_title      TEXT        NOT NULL,
    reason           TEXT        NOT NULL CHECK (char_length(reason) BETWEEN 1 AND 2000),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (proposal_id, weber_account_id)
);

-- Genau eine aktuelle, änderbare Stimme je Weber und Antrag (Upsert über PK).
CREATE TABLE governance_votes (
    proposal_id      UUID        NOT NULL REFERENCES governance_proposals (id) ON DELETE CASCADE,
    voter_account_id TEXT        NOT NULL,
    choice           TEXT        NOT NULL CHECK (choice IN ('ja', 'nein', 'enthaltung')),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (proposal_id, voter_account_id)
);

-- Gesprächsraum: Beiträge sind Webungsaktionen (nur Weber/Admin schreiben).
CREATE TABLE governance_messages (
    id                UUID        PRIMARY KEY,
    proposal_id       UUID        NOT NULL REFERENCES governance_proposals (id) ON DELETE CASCADE,
    author_account_id TEXT        NOT NULL,
    author_title      TEXT        NOT NULL,
    body              TEXT        NOT NULL CHECK (char_length(body) BETWEEN 1 AND 4000),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX governance_messages_by_proposal
    ON governance_messages (proposal_id, created_at, id);

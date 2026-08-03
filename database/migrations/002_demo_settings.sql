-- Demo clock ("today" override) used by /api/demo/today — needed by F2/F5 demos.
CREATE TABLE demo_settings (
  id int PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  today date NOT NULL DEFAULT CURRENT_DATE
);
INSERT INTO demo_settings (id, today) VALUES (1, CURRENT_DATE) ON CONFLICT DO NOTHING;

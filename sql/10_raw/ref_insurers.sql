-- Short name and role per insurer. role is 'focus' (the company the cockpit steers)
-- or 'peer' (the company it is compared with); the peer gap reads it.
CREATE OR REPLACE TABLE ref_insurers AS
SELECT insurer, insurer_short, role
FROM read_csv(
    getvariable('reference_dir') || '/insurers.csv',
    header = true,
    auto_detect = false,
    columns = {'insurer': 'VARCHAR', 'insurer_short': 'VARCHAR', 'role': 'VARCHAR'}
)
ORDER BY insurer;

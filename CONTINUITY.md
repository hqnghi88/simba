# Continuity Ledger

- Goal: Rebrand the project from `simba` to `kms` throughout the entire codebase (files, directories, contents).
- Constraints/Assumptions:
    - Case-sensitive search needed for "simba", "Simba", "SIMBA".
    - Need to handle file/directory renames cautiously to avoid breaking paths.
- State:
    - Done: Fixed Vite host blocking.
    - Now: Searching for all occurrences of 'simba' in contents and filenames.
    - Next: Perform massive find-and-replace and directory renaming.
- Open questions:
    - Are you accessing the platform from the Linux server's own browser or from a remote computer?
    - Does `docker compose ps` show all services as 'Up (healthy)'?
    - Is `VITE_API_URL` in your `.env` file set to the server's public IP or `localhost`?
- Working set:
    - `install_linux.sh`
    - `docker/docker-compose.yml`
    - `.env`
    - `frontend/src/lib/http/client.ts`

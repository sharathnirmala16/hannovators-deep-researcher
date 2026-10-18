# Future seed material storage

This plan describes future product work. The current scaffold contains no seed registry or ingestion code.

- Store the SQLite database at root `data/hannovators.db`.
- Store each seed material's files under `data/seeds/<UUID>/`.
- Add a `seed_materials` database table through a new Alembic revision.
- Give each material a UUID primary key and a unique path to its directory or file.
- Store paths relative to root `data/`, such as `seeds/<UUID>/source.pdf`.
- Enforce unique IDs and paths with database constraints. Keep paths inside `data/seeds/`.
- Keep runtime database files and seed material out of Git.
- Add tests for duplicate IDs, duplicate paths, path validation, and the schema migration with that work.

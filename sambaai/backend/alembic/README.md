<!-- ONYX_METADATA={"link": "https://github.com/sambaai-dot-app/sambaai/blob/main/backend/alembic/README.md"} -->

# Alembic DB Migrations

These files are for creating/updating the tables in the Relational DB (Postgres).
SambaAI migrations use a generic single-database configuration with an async dbapi.

## To generate new migrations:

run from sambaai/backend:
`alembic revision --autogenerate -m <DESCRIPTION_OF_MIGRATION>`

More info can be found here: https://alembic.sqlalchemy.org/en/latest/autogenerate.html

## Running migrations

To run all un-applied migrations:
`alembic upgrade head`

To undo migrations:
`alembic downgrade -X`
where X is the number of migrations you want to undo from the current state

.PHONY: dev migrate migrate-new

dev:
	uvicorn app.main:app --reload --reload-dir app --reload-dir shared

migrate:
	alembic upgrade head

migrate-new:
	alembic revision --autogenerate -m "$(msg)"

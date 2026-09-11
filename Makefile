.PHONY: install generate-data run test lint docker-run

install:
	pip install -e ".[dev]" 2>/dev/null || { pip install -r requirements-dev.txt && pip install -e .; }

generate-data:
	python -m crm_sop_planning.cli generate-data --seed 42

run:
	python -m crm_sop_planning.cli run

export-dashboard:
	python scripts/export_dashboard_data.py

test:
	pytest -v --cov=crm_sop_planning --cov-report=term-missing

lint:
	flake8 src tests scripts --max-line-length=100 --extend-ignore=E203
	black --check src tests scripts

docker-run:
	docker compose up --build planning

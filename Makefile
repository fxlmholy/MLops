.PHONY: install pipeline train serve down test lint loadtest drift rollback

install:
	pip install -r requirements.txt

pipeline:        ## P7: รันทั้ง DAG raw -> serving
	python -m src.flow

train:
	python -m src.train

serve:           ## P5: เปิดทุก service
	docker compose up -d --build

down:
	docker compose down

lint:
	ruff check .

test: lint
	pytest -q

loadtest:        ## P5: วัด p50/p95/RPS
	locust -f loadtest/locustfile.py --headless -u 50 -r 10 -t 60s --host http://localhost:8000 --csv docs/evidence/loadtest

drift:           ## P6
	python -m src.simulate_drift && python -m src.monitor

rollback:        ## P4
	python -m src.registry rollback

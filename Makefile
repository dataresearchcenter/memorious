DOCKER=docker run -v $(PWD)/dist:/memorious/dist -ti ghcr.io/dataresearchcenter/memorious
COMPOSE=docker compose -f docker-compose.dev.yml

HTTPBIN := http://localhost:80


.PHONY: all clean build dev rebuild test services shell image

all: clean

install:
	poetry install --with dev --all-extras

clean:
	rm -rf dist build .eggs
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +

build:
	docker build -t ghcr.io/dataresearchcenter/memorious .

dev:
	$(COMPOSE) build
	$(COMPOSE) run shell

rebuild:
	docker build --pull --no-cache -t ghcr.io/dataresearchcenter/memorious .

lint:
	poetry run flake8 memorious --count --select=E9,F63,F7,F82 --show-source --statistics
	poetry run flake8 memorious --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

pre-commit:
	poetry run pre-commit install
	poetry run pre-commit run -a

typecheck:
	poetry run mypy --strict memorious

test:
	# Check if the command works
	poetry run memorious list
	poetry run pytest -v --capture=sys --cov=memorious --cov-report lcov

services:
	$(COMPOSE) up -d httpbin proxy

shell:
	$(COMPOSE) run shell

image:
	docker build -t ghcr.io/dataresearchcenter/memorious .

documentation:
	mkdocs build
	aws --profile nbg1 --endpoint-url https://s3.investigativedata.org s3 sync ./site s3://docs.investigraph.dev/lib/memorious

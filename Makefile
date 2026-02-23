.PHONY: build test clean

build:
	docker compose build

test:
	docker compose up --exit-code-from tests

clean:
	docker compose down -v
	rm -rf .venv

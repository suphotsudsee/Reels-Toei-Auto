.PHONY: config up down logs smoke

config:
	docker compose config -q

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=200 api worker beat

smoke:
	bash scripts/smoke-test.sh

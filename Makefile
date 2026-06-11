.PHONY: lint test build publish clean

lint:
	ruff check .

test:
	pytest

build:
	python -m build

publish: build
	twine upload dist/*

clean:
	rm -rf dist/ build/ *.egg-info
	rm -rf .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

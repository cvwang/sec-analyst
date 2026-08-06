.PHONY: test eval-all eval-live benchmark

test:
	pytest eval/

eval-all:
	python -m eval.run_benchmark --regression-check

eval-live:
	python -m eval.run_benchmark --live --regression-check

benchmark:
	python -m eval.run_benchmark --mocked


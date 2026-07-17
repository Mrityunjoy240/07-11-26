.PHONY: install run test clean

install:
	cd backend && pip install -r requirements.txt

run:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	cd backend && python -m pytest tests/

clean:
	rm -rf __pycache__ .pytest_cache chroma_db temp_audio logs backups
	find . -name "*.pyc" -delete

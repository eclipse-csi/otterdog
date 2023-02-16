init:
	test -d venv || python3 -m venv venv
	( \
       . venv/bin/activate; \
       pip3 install -r requirements.txt; \
       playwright install chromium \
    )

test:
	( \
       . venv/bin/activate; \
       pytest tests \
    )

clean:
	rm -rf venv
	find -iname "*.pyc" -delete

.PHONY: init test clean

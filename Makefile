init:
	test -d venv || python3 -m venv venv
	( \
       . venv/bin/activate; \
       pip3 install -r requirements.txt; \
       playwright install chromium \
    )

  	ifeq (, $(shell which bw))
 		$(error "No bitwarden cli tool in your PATH, consider doing 'snap install bw'")
 	endif

test:
	( \
       . venv/bin/activate; \
       pytest tests \
    )

clean:
	rm -rf venv
	find -iname "*.pyc" -delete

.PHONY: init test clean

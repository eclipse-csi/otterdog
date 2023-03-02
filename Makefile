init:
	test -d venv || python3 -m venv venv
	( \
       . venv/bin/activate; \
       pip3 install -r requirements.txt; \
       playwright install chromium \
    )

  	ifeq (, $(shell which bw))
 		$(error "No bitwarden cli tool in your PATH, install it using 'snap install bw'")
 	endif

  	ifeq (, $(shell which pass))
 		$(error "No pass cli tool in your PATH, install it using 'apt install pass'")
 	endif

  	ifeq (, $(shell which jb))
 		$(error "No jsonnet-bundler tool in your PATH, install it using 'go install -a github.com/jsonnet-bundler/jsonnet-bundler/cmd/jb@latest'")
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

# Local testing

## One time setup
* brew install kind
* Ensure you have no config at ~/.kube/config
* kind create cluster
* mv ~/.kube/config ~/.kube/kind-config

## Automated install and test with ct
* export KUBECONFIG=~/.kube/kind-config
* kubectl config use-context kind-kind
* from source root run the following. This does a very basic test against the web server
  * ct install --all --helm-extra-set-args="--set=nginx.enabled=false" --debug --config ct.yaml

## Test the entire cluster manually
* helm install sambaai . -n sambaai --set postgresql.primary.persistence.enabled=false
  * the postgres flag is to keep the storage ephemeral for testing, you probably don't want to set that in prod
  * no flag for ephemeral vespa storage yet, might be good for testing
* kubectl -n sambaai port-forward service/sambaai-nginx 8080:80
  * this will forward the local port 8080 to the installed chart for you to run tests, etc.
* When you are finished
  * helm uninstall sambaai -n sambaai
  * Vespa leaves behind a PVC - delete it if you are completely done
    * k -n sambaai get pvc
    * k -n sambaai delete pvc vespa-storage-da-vespa-0
  * If you didn't disable Postgres persistence earlier, you may want to delete that PVC too.
<!-- ONYX_METADATA={"link": "https://github.com/sambaai-dot-app/sambaai/blob/main/deployment/README.md"} -->

# Deploying SambaAI

The two options provided here are the easiest ways to get SambaAI up and running.

- Docker Compose is simpler and default values are already preset to run right out of the box with a single command.
  As everything is running on a single machine, this may not be as scalable depending on your hardware, traffic and needs.

- Kubernetes deployment is also provided. Depending on your existing infrastructure, this may be more suitable for
  production deployment but there are a few caveats.
  - User auth is turned on by default for Kubernetes (with the assumption this is for production use)
    so you must either update the deployments to turn off user auth or provide the values shown in the example
    secrets.yaml file.
  - The example provided assumes a blank slate for existing Kubernetes deployments/services. You may need to adjust the
    deployments or services according to your setup. This may require existing Kubernetes knowledge or additional
    setup time.

All the features of SambaAI are fully available regardless of the deployment option.

For information on setting up connectors, check out https://docs.sambaai.app/connectors/overview

## Docker Compose:

Docker Compose provides the easiest way to get SambaAI up and running.

Requirements: Docker and docker compose

This section is for getting started quickly without setting up GPUs. For deployments to leverage GPU, please refer to [this](https://github.com/sambaai-dot-app/sambaai/blob/main/deployment/docker_compose/README.md) documentation.

1. To run SambaAI, navigate to `docker_compose` directory and run the following:

   - `docker compose -f docker-compose.dev.yml -p sambaai-stack up -d --pull always --force-recreate` - or run: `docker compose -f docker-compose.dev.yml -p sambaai-stack up -d --build --force-recreate`
     to build from source
   - Downloading images or packages/requirements may take 15+ minutes depending on your internet connection.

2. To shut down the deployment, run:

   - To stop the containers: `docker compose -f docker-compose.dev.yml -p sambaai-stack stop`
   - To delete the containers: `docker compose -f docker-compose.dev.yml -p sambaai-stack down`

3. To completely remove SambaAI run:
   - **WARNING, this will also erase your indexed data and users**
   - `docker compose -f docker-compose.dev.yml -p sambaai-stack down -v`

Additional steps for user auth and https if you do want to use Docker Compose for production:

1. Set up a `.env` file in this directory with relevant environment variables.

   - Refer to `env.prod.template`
   - To turn on user auth, set:
     - GOOGLE_OAUTH_CLIENT_ID=\<your GCP API client ID\>
     - GOOGLE_OAUTH_CLIENT_SECRET=\<associated client secret\>
     - Refer to https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid

2. Set up https:

   - Set up a `.env.nginx` file in this directory based on `env.nginx.template`.
   - `chmod +x init-letsencrypt.sh` + `./init-letsencrypt.sh` to set up https certificate.

3. Follow the above steps but replacing dev with prod.

## Kubernetes:

Depending on your deployment needs Kubernetes may be more suitable. The yamls provided will work out of the box but the
intent is for you to customize the deployment to fit your own needs. There is no data replication or auto-scaling built
in for the provided example.

Requirements: a Kubernetes cluster and kubectl

**NOTE: This setup does not explicitly enable https, the assumption is you would have this already set up for your
prod cluster**

1. To run SambaAI, navigate to `kubernetes` directory and run the following:

   - `kubectl apply -f .`

2. To remove SambaAI, run:
   - **WARNING, this will also erase your indexed data and users**
   - `kubectl delete -f .`
   - To not delete the persistent volumes (Document indexes and Users), specify the specific `.yaml` files instead of
     `.` without specifying delete on persistent-volumes.yaml.

### Using Helm to deploy to an existing cluster

SambaAI has a helm chart that is convenient to install all services to an existing Kubernetes cluster. To install:

* Currently the helm chart is not published so to install, clone the repo.
* Configure access to the cluster via kubectl. Ensure the kubectl context is set to the cluster that you want to use
* The default secrets, environment variables and other service level configuration are stored in `deployment/helm/charts/sambaai/values.yml`. You may create another `override.yml`
* `cd deployment/helm/charts/sambaai` and run `helm install sambaai -n sambaai -f override.yaml .`. This will install sambaai on the cluster under the `sambaai` namespace.
* Check the status of the deploy using `kubectl get pods -n sambaai`